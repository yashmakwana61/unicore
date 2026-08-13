import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OacisAcademicYear(models.Model):
    """Academic Year representing the annual academic calendar."""

    _name = 'oacis.academic.year'
    _description = 'Academic Year'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'
    _check_company_auto = True

    name = fields.Char(
        string='Academic Year',
        required=True,
        help='e.g. 2024-2025, AY-2025',
        tracking=True,
    )
    code = fields.Char(
        string='Year Code',
        required=True,
        size=20,
        help='e.g. AY2425, 2024-25',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )
    campus_ids = fields.Many2many(
        comodel_name='oacis.campus',
        relation='oacis_academic_year_campus_rel',
        column1='academic_year_id',
        column2='campus_id',
        string='Applicable Campuses',
        help='Leave empty to apply to all campuses',
    )
    date_start = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
    )
    date_end = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
    )
    year_type = fields.Selection(
        selection=[
            ('semester', 'Semester Based'),
            ('trimester', 'Trimester Based'),
            ('quarter', 'Quarter Based'),
            ('annual', 'Annual'),
            ('term', 'Term Based'),
        ],
        string='Year Structure',
        default='semester',
        required=True,
        tracking=True,
    )
    semester_ids = fields.One2many(
        comodel_name='oacis.semester',
        inverse_name='academic_year_id',
        string='Semesters / Terms',
    )
    holiday_ids = fields.One2many(
        comodel_name='oacis.holiday',
        inverse_name='academic_year_id',
        string='Holidays',
    )
    semester_count = fields.Integer(
        string='Total Semesters',
        compute='_compute_semester_count',
        store=True,
    )
    week_count = fields.Integer(
        string='Total Weeks',
        compute='_compute_week_count',
        store=False,
    )
    holiday_count = fields.Integer(
        string='Total Holidays',
        compute='_compute_holiday_count',
        store=True,
    )
    total_working_days = fields.Integer(
        string='Total Working Days',
        compute='_compute_total_working_days',
        store=False,
    )
    year_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('active', 'Active / Current'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    is_current = fields.Boolean(
        string='Is Current Year',
        compute='_compute_is_current',
        store=True,
    )
    previous_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Previous Academic Year',
        domain="[('company_id', '=', company_id)]",
        help='Link to the preceding academic year',
    )
    next_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Next Academic Year',
        domain="[('company_id', '=', company_id)]",
        help='Link to the following academic year',
    )

    _unique_year_code_company = models.Constraint(
        'UNIQUE(code, company_id)',
        'Academic year code must be unique per institution.',
    )

    # Semester types allowed inside a Term-based academic year (Phase 8).
    _TERM_SEMESTER_TYPES = ('term_1', 'term_2', 'term_3', 'term_4')

    @api.depends('semester_ids')
    def _compute_semester_count(self):
        for record in self:
            record.semester_count = len(record.semester_ids)

    @api.depends('holiday_ids')
    def _compute_holiday_count(self):
        for record in self:
            record.holiday_count = len(record.holiday_ids)

    def _compute_week_count(self):
        week_model = self.env['oacis.academic.week']
        for record in self:
            record.week_count = week_model.search_count(
                [('academic_year_id', '=', record.id)],
            )

    def _compute_total_working_days(self):
        holiday_model = self.env['oacis.holiday']
        for record in self:
            if record.date_start and record.date_end:
                total = (record.date_end - record.date_start).days + 1
                holidays = holiday_model.search([
                    ('academic_year_id', '=', record.id),
                    ('date_start', '>=', record.date_start),
                    ('date_end', '<=', record.date_end),
                    ('affects_attendance', '=', True),
                ])
                holiday_days = sum(
                    (h.date_end - h.date_start).days + 1 for h in holidays
                )
                record.total_working_days = max(total - holiday_days, 0)
            else:
                record.total_working_days = 0

    @api.depends('year_state', 'date_start', 'date_end')
    def _compute_is_current(self):
        today = date.today()
        for record in self:
            record.is_current = bool(
                record.year_state == 'active'
                and record.date_start
                and record.date_end
                and record.date_start <= today <= record.date_end,
            )

    @api.constrains('date_start', 'date_end')
    def _check_date_range(self):
        for record in self:
            if record.date_start and record.date_end:
                if record.date_end <= record.date_start:
                    raise ValidationError(
                        _('End date must be after start date.'),
                    )

    @api.constrains('date_start', 'date_end', 'year_state', 'company_id')
    def _check_overlap_active(self):
        for record in self:
            if record.year_state not in ('cancelled',) and record.date_start and record.date_end:
                overlapping = self.search([
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id),
                    ('year_state', 'not in', ('cancelled',)),
                    ('date_start', '<', record.date_end),
                    ('date_end', '>', record.date_start),
                ])
                if overlapping:
                    raise ValidationError(
                        _('Academic year dates cannot overlap with another academic year for the same institution.'),
                    )

    @api.constrains('year_state', 'company_id')
    def _check_single_active(self):
        for record in self:
            if record.year_state == 'active':
                other_active = self.search([
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id),
                    ('year_state', '=', 'active'),
                ])
                if other_active:
                    raise ValidationError(
                        _('Only one academic year can be active per institution at a time.'),
                    )

    @api.model_create_multi
    def create(self, vals_list):
        # A term-mode institution gets a sensible default year structure.
        for vals in vals_list:
            if 'year_type' not in vals:
                company = self.env['res.company'].browse(
                    vals.get('company_id') or self.env.company.id)
                profile = company.institution_profile_id
                if profile and profile.calendar_mode == 'term':
                    vals['year_type'] = 'term'
        records = super().create(vals_list)
        records._check_term_structure()
        records._check_calendar_mode()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'year_type' in vals or 'semester_ids' in vals:
            self._check_term_structure()
        if 'year_type' in vals or 'company_id' in vals:
            self._check_calendar_mode()
        return result

    def _check_calendar_mode(self):
        """A term-mode institution may only create Term-based academic years.

        One-directional: a company whose profile is term-based must use
        ``year_type == 'term'``; semester/other profiles stay fully flexible
        (legacy behavior preserved).
        """
        for record in self:
            profile = record.company_id.institution_profile_id
            if profile and profile.calendar_mode == 'term' \
                    and record.year_type != 'term':
                raise ValidationError(
                    _('Institution profile "%(profile)s" uses a Term-based '
                      'calendar; academic years must be "Term Based".',
                      profile=profile.name),
                )

    def _check_term_structure(self):
        """A Term-based academic year may only contain Term semesters.

        Legacy-inert: only fires when ``year_type == 'term'`` is set explicitly.
        """
        for record in self:
            if record.year_type == 'term':
                bad = record.semester_ids.filtered(
                    lambda s: s.semester_type not in self._TERM_SEMESTER_TYPES)
                if bad:
                    raise ValidationError(
                        _('A Term-based academic year can only contain Term '
                          'semesters (First/Second/Third/Fourth Term).'),
                    )

    def action_confirm(self):
        self.ensure_one()
        if not self.date_start or not self.date_end:
            raise UserError(_('Start date and end date must be set before confirmation.'))
        if not self.semester_ids:
            raise UserError(_('At least one semester must exist before confirming the academic year.'))
        self.year_state = 'confirmed'

    def action_activate(self):
        self.ensure_one()
        other_active = self.search([
            ('company_id', '=', self.company_id.id),
            ('id', '!=', self.id),
            ('year_state', '=', 'active'),
        ])
        for previous in other_active:
            previous.year_state = 'completed'
            _logger.info(
                'Academic year %s (%s) auto-completed when %s (%s) was activated.',
                previous.name, previous.code, self.name, self.code,
            )
        self.year_state = 'active'

    def action_complete(self):
        self.ensure_one()
        self.year_state = 'completed'

    def action_cancel(self):
        self.ensure_one()
        self.year_state = 'cancelled'

    def action_reset_draft(self):
        self.ensure_one()
        self.year_state = 'draft'

    def action_open_semesters(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Semesters'),
            'res_model': 'oacis.semester',
            'view_mode': 'list,form',
            'domain': [('academic_year_id', '=', self.id)],
            'context': {'default_academic_year_id': self.id},
        }

    def action_open_weeks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Academic Weeks'),
            'res_model': 'oacis.academic.week',
            'view_mode': 'list,form',
            'domain': [('academic_year_id', '=', self.id)],
            'context': {'default_academic_year_id': self.id},
        }

    def action_open_holidays(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Holidays'),
            'res_model': 'oacis.holiday',
            'view_mode': 'list,form',
            'domain': [('academic_year_id', '=', self.id)],
            'context': {'default_academic_year_id': self.id},
        }

    @api.model
    def get_current_year(self, company_id=None):
        company = company_id or self.env.company.id
        current = self.search([
            ('company_id', '=', company),
            ('year_state', '=', 'active'),
            ('date_start', '<=', date.today()),
            ('date_end', '>=', date.today()),
        ], limit=1)
        return current
