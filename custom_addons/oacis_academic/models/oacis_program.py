import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OacisProgram(models.Model):
    """Academic Program representing a Degree, Diploma or Certificate."""

    _name = 'oacis.program'
    _description = 'Academic Program (Degree / Diploma / Certificate)'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'department_id, sequence, name'
    _check_company_auto = True

    name = fields.Char(
        string='Program Name',
        required=True,
        translate=True,
        help='e.g. Bachelor of Computer Science',
    )
    code = fields.Char(
        string='Program Code',
        required=True,
        size=20,
        help='e.g. BSCS, MBA, MTECH-CS',
    )
    department_id = fields.Many2one(
        comodel_name='oacis.department',
        string='Department',
        # Not required at the ORM level anymore (Phase 1 makes the rigid
        # Faculty -> Department -> Program chain optional for non-university
        # institutions). `_check_program_anchor` re-enforces the legacy
        # requirement (Department mandatory) via the is_legacy_university shim,
        # so the legacy university path stays 100% identical.
        ondelete='restrict',
        tracking=True,
    )
    academic_unit_id = fields.Many2one(
        comodel_name='oacis.academic.unit',
        string='Academic Unit',
        ondelete='restrict',
        tracking=True,
        domain="[('company_id', '=', company_id)]",
        help='Generic academic unit (Grade Level, Wing, Batch Group, ...) that '
             'this program / class / cohort attaches to for non-university '
             'institutions. Universities keep using Department (legacy).',
    )
    faculty_id = fields.Many2one(
        comodel_name='oacis.faculty',
        related='department_id.faculty_id',
        string='Faculty',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        compute='_compute_company_id',
        string='Institution',
        store=True,
        readonly=True,
        help='Derived from the Department (legacy) or the Academic Unit anchor.',
    )
    program_type = fields.Selection(
        selection=[
            ('undergraduate', 'Undergraduate'),
            ('postgraduate', 'Postgraduate'),
            ('doctoral', 'Doctoral / PhD'),
            ('diploma', 'Diploma'),
            ('certificate', 'Certificate'),
            ('professional', 'Professional Degree'),
            ('integrated', 'Integrated Program'),
            ('online', 'Online / Distance'),
        ],
        string='Program Type',
        default='undergraduate',
        required=True,
        tracking=True,
    )
    degree_title = fields.Char(
        string='Degree Title',
        required=True,
        help='Official title awarded e.g. Bachelor of Science',
    )
    duration_years = fields.Float(
        string='Duration (Years)',
        required=True,
        default=4.0,
        digits=(4, 1),
        help='e.g. 3.5 for 3 years 6 months',
    )
    credit_system = fields.Selection(
        selection=[
            ('credit_hours', 'Credit Hours'),
            ('credit_points', 'Credit Points'),
            ('semester_based', 'Semester Based'),
            ('annual', 'Annual'),
        ],
        string='Credit System',
        default='credit_hours',
        required=True,
    )
    total_credits = fields.Integer(
        string='Total Credits Required',
        default=120,
        help='Minimum credits required to complete the program',
    )
    semesters_count = fields.Integer(
        string='Number of Semesters',
        compute='_compute_semesters_count',
        store=False,
    )
    campus_ids = fields.Many2many(
        comodel_name='oacis.campus',
        relation='oacis_program_campus_rel',
        column1='program_id',
        column2='campus_id',
        string='Offered at Campuses',
    )
    specialisation_ids = fields.One2many(
        comodel_name='oacis.specialisation',
        inverse_name='program_id',
        string='Specialisations',
    )
    specialisation_count = fields.Integer(
        string='Specialisation Count',
        compute='_compute_specialisation_count',
        store=True,
    )
    program_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('active', 'Active'),
            ('discontinued', 'Discontinued'),
        ],
        string='Program Status',
        default='draft',
        required=True,
        tracking=True,
    )
    accreditation_status = fields.Selection(
        selection=[
            ('not_accredited', 'Not Accredited'),
            ('pending', 'Accreditation Pending'),
            ('accredited', 'Accredited'),
            ('expired', 'Accreditation Expired'),
        ],
        string='Accreditation Status',
        default='not_accredited',
        tracking=True,
    )
    accreditation_body = fields.Char(
        string='Accrediting Body',
    )
    accreditation_expiry = fields.Date(
        string='Accreditation Expiry Date',
    )
    min_entry_qualification = fields.Text(
        string='Minimum Entry Qualification',
        help='Minimum academic qualification required for admission',
    )
    tuition_fee_per_semester = fields.Float(
        string='Tuition Fee Per Semester',
        digits=(14, 2),
        help='Base tuition fee — actual invoicing handled by oacis_fees',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    coordinator_id = fields.Many2one(
        comodel_name='res.users',
        string='Program Coordinator',
        tracking=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    description = fields.Html(
        string='Program Overview',
    )
    learning_outcomes = fields.Html(
        string='Learning Outcomes',
    )

    _unique_program_code_company = models.Constraint(
        'UNIQUE(code, company_id)',
        'Program code must be unique per institution.',
    )

    is_legacy_institution = fields.Boolean(
        string='Legacy University Institution',
        compute='_compute_is_legacy_institution',
        help='True when the program belongs to a company without an institution '
             'profile, or whose profile is in legacy university mode. In legacy '
             'mode the Department is mandatory (Phase 1 compatibility shim).',
    )
    cohort_kind = fields.Selection(
        selection=[
            ('academic_year', 'Academic Year / Batch'),
            ('grade_batch', 'Grade-Level Batch'),
            ('rolling', 'Rolling Intake'),
        ],
        string='Cohort Kind',
        default='academic_year',
        tracking=True,
        help='How students are grouped into cohorts for this program (Phase 3). '
             'Legacy universities keep Academic Year / Batch (students grouped '
             'by admission year). K-12 schools use Grade-Level Batch; training '
             '/ coaching centres use Rolling Intake.',
    )
    cohort_grouping_label = fields.Char(
        string='Cohort Grouping',
        compute='_compute_cohort_grouping_label',
        help='Human-readable description of how students are grouped.',
    )

    @api.depends('cohort_kind')
    def _compute_cohort_grouping_label(self):
        labels = {
            'academic_year': 'Grouped by admission academic year (batch)',
            'grade_batch': 'Grouped by grade level within the academic year',
            'rolling': 'Rolling intake cohorts by start date',
        }
        for record in self:
            record.cohort_grouping_label = labels.get(
                record.cohort_kind, '',
            )

    @api.depends('department_id.company_id', 'academic_unit_id.company_id')
    def _compute_company_id(self):
        for record in self:
            record.company_id = (
                record.department_id.company_id
                or record.academic_unit_id.company_id
                or False
            )

    @api.depends('company_id.institution_profile_id.is_legacy_university')
    def _compute_is_legacy_institution(self):
        for record in self:
            profile = record.company_id.institution_profile_id
            record.is_legacy_institution = not profile or profile.is_legacy_university

    def _check_program_anchor(self):
        """Phase 1 compatibility shim for the academic hierarchy.

        * Legacy university (or unset profile)  -> Department is mandatory.
        * Any other institution type            -> at least one anchor
          (Department and/or Academic Unit) is mandatory.

        NOTE: this is invoked from `create()`/`write()` rather than
        `@api.constrains`, because a constrain on ('department_id',
        'academic_unit_id') never fires on create when neither field is
        supplied in the vals (both are optional at the ORM level now).
        """
        for record in self:
            company = (
                record.department_id.company_id
                or record.academic_unit_id.company_id
                or record.company_id
            )
            profile = company.institution_profile_id if company else False
            legacy = not profile or profile.is_legacy_university
            if legacy:
                if not record.department_id:
                    raise ValidationError(
                        _('A Department is required for programs of a '
                          'university (legacy) institution.'),
                    )
            elif not record.department_id and not record.academic_unit_id:
                raise ValidationError(
                    _('A program must be attached to either a Department '
                      'or an Academic Unit.'),
                )

    def _check_cohort_kind(self):
        """Phase 3: legacy universities are locked to academic_year cohorts.

        K-12 / training / coaching institutions may use grade_batch or rolling.
        Invoked from `create()`/`write()` like `_check_program_anchor`, because
        a constrains hook on ('cohort_kind') would not fire on anchor-less
        create when the field is absent from vals.
        """
        for record in self:
            if (record.is_legacy_institution
                    and record.cohort_kind != 'academic_year'):
                raise ValidationError(
                    _('University (legacy) institutions can only use '
                      'Academic Year / Batch cohorts.'),
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_program_anchor()
        records._check_cohort_kind()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'department_id' in vals or 'academic_unit_id' in vals:
            self._check_program_anchor()
        if 'cohort_kind' in vals:
            self._check_cohort_kind()
        return res

    @api.depends('specialisation_ids')
    def _compute_specialisation_count(self):
        for record in self:
            record.specialisation_count = len(record.specialisation_ids)

    def _compute_semesters_count(self):
        for record in self:
            record.semesters_count = int(record.duration_years * 2)

    @api.constrains('duration_years')
    def _check_duration_years(self):
        for record in self:
            if record.duration_years <= 0:
                raise ValidationError(
                    _('Duration must be greater than zero.'),
                )
            if record.duration_years > 10:
                raise ValidationError(
                    _('Duration cannot exceed 10 years.'),
                )

    @api.constrains('total_credits')
    def _check_total_credits(self):
        for record in self:
            if record.total_credits <= 0:
                raise ValidationError(
                    _('Total credits must be greater than zero.'),
                )

    @api.constrains('accreditation_expiry', 'accreditation_status')
    def _check_accreditation_expiry(self):
        for record in self:
            if record.accreditation_status == 'accredited' and record.accreditation_expiry:
                if record.accreditation_expiry < date.today():
                    raise ValidationError(
                        _('Accreditation expiry date must be in the future.'),
                    )

    @api.onchange('duration_years')
    def _onchange_duration_years(self):
        if self.duration_years:
            self.semesters_count = int(self.duration_years * 2)
            return {
                'warning': {
                    'title': _('Semesters Calculated'),
                    'message': _(
                        'Based on the duration of %(years)s year(s), '
                        'the program will have %(semesters)s semesters.',
                        years=self.duration_years,
                        semesters=self.semesters_count,
                    ),
                },
            }

    def action_approve(self):
        self.ensure_one()
        if not self.duration_years:
            raise UserError(_('Duration must be set before approval.'))
        if not self.total_credits or self.total_credits <= 0:
            raise UserError(_('Total credits must be set before approval.'))
        if not self.degree_title:
            raise UserError(_('Degree title must be set before approval.'))
        self.program_state = 'approved'

    def action_activate(self):
        self.ensure_one()
        if not self.campus_ids:
            raise UserError(
                _('At least one campus must be assigned before activating the program.'),
            )
        self.program_state = 'active'

    def action_discontinue(self):
        self.ensure_one()
        self.program_state = 'discontinued'
        _logger.info(
            'Program %s (%s) has been discontinued.',
            self.name, self.code,
        )

    def action_reset_draft(self):
        self.ensure_one()
        self.program_state = 'draft'

    def action_open_specialisations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Specialisations'),
            'res_model': 'oacis.specialisation',
            'view_mode': 'list,form',
            'domain': [('program_id', '=', self.id)],
            'context': {'default_program_id': self.id},
        }
