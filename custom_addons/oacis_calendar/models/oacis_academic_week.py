import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UnicoreAcademicWeek(models.Model):
    """Academic Week within a Semester."""

    _name = 'unicore.academic.week'
    _description = 'Academic Week'
    _inherit = ['unicore.mixin']
    _order = 'semester_id, week_number'
    _check_company_auto = True

    name = fields.Char(
        string='Week Name',
        required=True,
        help='e.g. Week 1, Teaching Week 3, Revision Week',
    )
    week_number = fields.Integer(
        string='Week Number',
        required=True,
        help='Sequential week number within semester',
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        required=True,
        ondelete='restrict',
    )
    academic_year_id = fields.Many2one(
        comodel_name='unicore.academic.year',
        related='semester_id.academic_year_id',
        string='Academic Year',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='semester_id.company_id',
        string='Institution',
        store=True,
        readonly=True,
    )
    date_start = fields.Date(
        string='Week Start Date',
        required=True,
        help='Usually Monday',
    )
    date_end = fields.Date(
        string='Week End Date',
        required=True,
        help='Usually Friday or Sunday',
    )
    week_type = fields.Selection(
        selection=[
            ('teaching', 'Teaching Week'),
            ('revision', 'Revision Week'),
            ('exam', 'Examination Week'),
            ('holiday', 'Holiday Week'),
            ('orientation', 'Orientation Week'),
            ('break', 'Semester Break'),
        ],
        string='Week Type',
        default='teaching',
        required=True,
    )
    is_current = fields.Boolean(
        string='Is Current Week',
        compute='_compute_is_current',
        store=True,
    )

    _unique_week_number_semester = models.Constraint(
        'UNIQUE(week_number, semester_id)',
        'Week number must be unique per semester.',
    )

    @api.depends('date_start', 'date_end')
    def _compute_is_current(self):
        today = date.today()
        for record in self:
            record.is_current = bool(
                record.date_start
                and record.date_end
                and record.date_start <= today <= record.date_end,
            )

    @api.constrains('date_start', 'date_end')
    def _check_date_range(self):
        for record in self:
            if record.date_start and record.date_end:
                if record.date_end < record.date_start:
                    raise ValidationError(
                        _('Week end date must be on or after start date.'),
                    )

    @api.constrains('date_start', 'date_end', 'semester_id')
    def _check_dates_within_semester(self):
        for record in self:
            if record.semester_id and record.date_start and record.date_end:
                sem = record.semester_id
                if record.date_start < sem.date_start:
                    raise ValidationError(
                        _('Week start date cannot be before the semester start date.'),
                    )
                if record.date_end > sem.date_end:
                    raise ValidationError(
                        _('Week end date cannot be after the semester end date.'),
                    )

    @api.constrains('date_start', 'date_end', 'semester_id')
    def _check_overlap_within_semester(self):
        for record in self:
            if record.semester_id and record.date_start and record.date_end:
                overlapping = self.search([
                    ('semester_id', '=', record.semester_id.id),
                    ('id', '!=', record.id),
                    ('date_start', '<', record.date_end),
                    ('date_end', '>', record.date_start),
                ])
                if overlapping:
                    raise ValidationError(
                        _('Week date ranges must not overlap within the same semester.'),
                    )
