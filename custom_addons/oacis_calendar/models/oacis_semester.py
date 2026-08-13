import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OacisSemester(models.Model):
    """Semester or Term within an Academic Year."""

    _name = 'oacis.semester'
    _description = 'Semester or Term'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id, sequence, date_start'
    _check_company_auto = True

    name = fields.Char(
        string='Semester Name',
        required=True,
        help='e.g. Fall 2024, Semester 1, Term A',
        tracking=True,
    )
    code = fields.Char(
        string='Semester Code',
        required=True,
        size=20,
        help='e.g. SEM1-2425, FALL24',
    )
    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='academic_year_id.company_id',
        string='Institution',
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of semester within the academic year',
    )
    semester_type = fields.Selection(
        selection=[
            ('odd', 'Odd Semester'),
            ('even', 'Even Semester'),
            ('summer', 'Summer Term'),
            ('winter', 'Winter Term'),
            ('trimester_1', 'First Trimester'),
            ('trimester_2', 'Second Trimester'),
            ('trimester_3', 'Third Trimester'),
            ('quarter_1', 'First Quarter'),
            ('quarter_2', 'Second Quarter'),
            ('quarter_3', 'Third Quarter'),
            ('quarter_4', 'Fourth Quarter'),
            ('annual', 'Annual'),
            ('term_1', 'First Term'),
            ('term_2', 'Second Term'),
            ('term_3', 'Third Term'),
            ('term_4', 'Fourth Term'),
        ],
        string='Semester Type',
        default='odd',
        required=True,
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
    registration_start = fields.Date(
        string='Registration Opens',
        help='Date when course registration opens for students',
    )
    registration_end = fields.Date(
        string='Registration Closes',
        help='Last date for course registration',
    )
    add_drop_end = fields.Date(
        string='Add/Drop Deadline',
        help='Last date to add or drop courses',
    )
    withdrawal_end = fields.Date(
        string='Withdrawal Deadline',
        help='Last date to withdraw from courses',
    )
    exam_start = fields.Date(
        string='Exam Period Start',
    )
    exam_end = fields.Date(
        string='Exam Period End',
    )
    result_declaration_date = fields.Date(
        string='Result Declaration Date',
    )
    week_ids = fields.One2many(
        comodel_name='oacis.academic.week',
        inverse_name='semester_id',
        string='Academic Weeks',
    )
    week_count = fields.Integer(
        string='Total Weeks',
        compute='_compute_week_count',
        store=True,
    )
    total_days = fields.Integer(
        string='Total Days',
        compute='_compute_total_days',
        store=False,
    )
    teaching_weeks = fields.Integer(
        string='Teaching Weeks',
        compute='_compute_teaching_weeks',
        store=False,
    )
    semester_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('registration', 'Registration Open'),
            ('ongoing', 'Ongoing'),
            ('exam', 'Examination Period'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    is_current = fields.Boolean(
        string='Is Current Semester',
        compute='_compute_is_current',
        store=True,
    )
    program_ids = fields.Many2many(
        comodel_name='oacis.program',
        relation='oacis_semester_program_rel',
        column1='semester_id',
        column2='program_id',
        string='Applicable Programs',
        help='Programs running in this semester',
    )

    _unique_semester_code_year = models.Constraint(
        'UNIQUE(code, academic_year_id)',
        'Semester code must be unique per academic year.',
    )

    @api.depends('week_ids')
    def _compute_week_count(self):
        for record in self:
            record.week_count = len(record.week_ids)

    @api.depends('date_start', 'date_end')
    def _compute_total_days(self):
        for record in self:
            if record.date_start and record.date_end:
                record.total_days = (record.date_end - record.date_start).days + 1
            else:
                record.total_days = 0

    @api.depends('week_ids', 'week_ids.week_type')
    def _compute_teaching_weeks(self):
        for record in self:
            record.teaching_weeks = len(
                record.week_ids.filtered(lambda w: w.week_type == 'teaching'),
            )

    @api.depends('semester_state', 'date_start', 'date_end')
    def _compute_is_current(self):
        today = date.today()
        for record in self:
            record.is_current = bool(
                record.semester_state in ('registration', 'ongoing', 'exam')
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
                        _('Semester end date must be after start date.'),
                    )

    @api.constrains('registration_start', 'registration_end')
    def _check_registration_dates(self):
        for record in self:
            if record.registration_start and record.registration_end:
                if record.registration_end <= record.registration_start:
                    raise ValidationError(
                        _('Registration end date must be after start date.'),
                    )

    @api.constrains('add_drop_end', 'date_start', 'date_end')
    def _check_add_drop_end(self):
        for record in self:
            if record.add_drop_end:
                if record.date_start and record.add_drop_end < record.date_start:
                    raise ValidationError(
                        _('Add/Drop deadline must be within the semester dates.'),
                    )
                if record.date_end and record.add_drop_end > record.date_end:
                    raise ValidationError(
                        _('Add/Drop deadline must be within the semester dates.'),
                    )

    @api.constrains('exam_start', 'exam_end')
    def _check_exam_dates(self):
        for record in self:
            if record.exam_start and record.exam_end:
                if record.exam_end <= record.exam_start:
                    raise ValidationError(
                        _('Exam end date must be after start date.'),
                    )
                if record.date_start and record.exam_start < record.date_start:
                    raise ValidationError(
                        _('Exam period must be within semester dates.'),
                    )
                if record.date_end and record.exam_end > record.date_end:
                    raise ValidationError(
                        _('Exam period must be within semester dates.'),
                    )

    @api.constrains('result_declaration_date', 'exam_end')
    def _check_result_date(self):
        for record in self:
            if record.result_declaration_date and record.exam_end:
                if record.result_declaration_date < record.exam_end:
                    raise ValidationError(
                        _('Result declaration date must be after exam end date.'),
                    )

    @api.constrains('date_start', 'date_end', 'academic_year_id')
    def _check_dates_within_academic_year(self):
        for record in self:
            if record.academic_year_id and record.date_start and record.date_end:
                ay = record.academic_year_id
                if record.date_start < ay.date_start:
                    raise ValidationError(
                        _('Semester start date cannot be before the academic year start date.'),
                    )
                if record.date_end > ay.date_end:
                    raise ValidationError(
                        _('Semester end date cannot be after the academic year end date.'),
                    )

    @api.constrains('academic_year_id', 'semester_type')
    def _check_term_semester_type(self):
        """A Term-based academic year may only contain Term semesters.

        Complements the year-level check and covers direct semester creation.
        Legacy-inert: only fires when the parent year is Term-based.
        """
        for record in self:
            if record.academic_year_id and record.academic_year_id.year_type == 'term':
                if record.semester_type not in (
                        self.env['oacis.academic.year']._TERM_SEMESTER_TYPES):
                    raise ValidationError(
                        _('A Term-based academic year can only contain Term '
                          'semesters (First/Second/Third/Fourth Term).'),
                    )

    def action_confirm(self):
        self.ensure_one()
        self.semester_state = 'confirmed'

    def action_open_registration(self):
        self.ensure_one()
        self.semester_state = 'registration'

    def action_start(self):
        self.ensure_one()
        self.semester_state = 'ongoing'

    def action_start_exam(self):
        self.ensure_one()
        self.semester_state = 'exam'

    def action_complete(self):
        self.ensure_one()
        self.semester_state = 'completed'

    def action_cancel(self):
        self.ensure_one()
        self.semester_state = 'cancelled'

    def action_reset_draft(self):
        self.ensure_one()
        self.semester_state = 'draft'

    def action_generate_weeks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Academic Weeks'),
            'res_model': 'oacis.generate.weeks.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_semester_id': self.id},
        }

    def action_open_weeks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Academic Weeks'),
            'res_model': 'oacis.academic.week',
            'view_mode': 'list,form',
            'domain': [('semester_id', '=', self.id)],
            'context': {'default_semester_id': self.id},
        }

    @api.model
    def get_current_semester(self, company_id=None):
        company = company_id or self.env.company.id
        academic_year = self.env['oacis.academic.year'].get_current_year(company)
        if not academic_year:
            return self.browse()
        current = self.search([
            ('academic_year_id', '=', academic_year.id),
            ('semester_state', 'in', ('registration', 'ongoing', 'exam')),
            ('date_start', '<=', date.today()),
            ('date_end', '>=', date.today()),
        ], limit=1)
        return current
