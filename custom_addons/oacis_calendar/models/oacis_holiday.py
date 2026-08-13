import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OacisHoliday(models.Model):
    """Academic Holiday or Event within an Academic Year."""

    _name = 'oacis.holiday'
    _description = 'Academic Holiday or Event'
    _inherit = ['oacis.mixin', 'mail.thread']
    _order = 'date_start'
    _check_company_auto = True

    name = fields.Char(
        string='Holiday / Event Name',
        required=True,
        translate=True,
        help='e.g. Diwali Break, Christmas Holidays, Foundation Day',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
    )
    semester_id = fields.Many2one(
        comodel_name='oacis.semester',
        string='Semester',
        ondelete='set null',
        domain="[('academic_year_id', '=', academic_year_id)]",
        help='Optional: link to specific semester',
    )
    campus_ids = fields.Many2many(
        comodel_name='oacis.campus',
        relation='oacis_holiday_campus_rel',
        column1='holiday_id',
        column2='campus_id',
        string='Applicable Campuses',
        help='Leave empty to apply to all campuses',
    )
    date_start = fields.Date(
        string='From Date',
        required=True,
        tracking=True,
    )
    date_end = fields.Date(
        string='To Date',
        required=True,
        tracking=True,
    )
    duration_days = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration_days',
        store=True,
    )
    holiday_type = fields.Selection(
        selection=[
            ('public', 'Public Holiday'),
            ('institutional', 'Institutional Holiday'),
            ('semester_break', 'Semester Break'),
            ('examination', 'Examination Holiday'),
            ('cultural', 'Cultural / Festival'),
            ('national', 'National Holiday'),
            ('emergency', 'Emergency Closure'),
            ('other', 'Other'),
        ],
        string='Holiday Type',
        default='public',
        required=True,
        tracking=True,
    )
    affects_attendance = fields.Boolean(
        string='Affects Attendance',
        default=True,
        help='If True attendance is not marked on these days',
    )
    is_compensatory = fields.Boolean(
        string='Compensatory Classes Required',
        default=False,
        help='If True compensatory classes must be scheduled',
    )
    description = fields.Text(
        string='Description / Reason',
    )

    @api.depends('date_start', 'date_end')
    def _compute_duration_days(self):
        for record in self:
            if record.date_start and record.date_end:
                record.duration_days = (record.date_end - record.date_start).days + 1
            else:
                record.duration_days = 0

    @api.constrains('date_start', 'date_end')
    def _check_date_range(self):
        for record in self:
            if record.date_start and record.date_end:
                if record.date_end < record.date_start:
                    raise ValidationError(
                        _('End date must be on or after start date.'),
                    )

    @api.constrains('date_start', 'date_end', 'academic_year_id')
    def _check_dates_within_academic_year(self):
        for record in self:
            if record.academic_year_id and record.date_start and record.date_end:
                ay = record.academic_year_id
                if record.date_start < ay.date_start:
                    raise ValidationError(
                        _('Holiday start date cannot be before the academic year start date.'),
                    )
                if record.date_end > ay.date_end:
                    raise ValidationError(
                        _('Holiday end date cannot be after the academic year end date.'),
                    )

    @api.constrains('date_start', 'date_end', 'holiday_type', 'company_id')
    def _check_overlap_warning(self):
        for record in self:
            if record.date_start and record.date_end:
                overlapping = self.search([
                    ('company_id', '=', record.company_id.id),
                    ('holiday_type', '=', record.holiday_type),
                    ('id', '!=', record.id),
                    ('date_start', '<', record.date_end),
                    ('date_end', '>', record.date_start),
                ])
                if overlapping:
                    _logger.warning(
                        'Holiday "%s" (%s) overlaps with another %s holiday.',
                        record.name, record.holiday_type, record.holiday_type,
                    )
