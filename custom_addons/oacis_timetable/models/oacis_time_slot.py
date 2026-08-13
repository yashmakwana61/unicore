"""
Oacis Time Slot Model
Defines reusable bell-schedule periods shared across
the institution. Time slots are day-agnostic templates
(e.g. "Period 1: 09:00-10:00") that are combined with
a day-of-week in oacis.timetable.entry to form
an actual scheduled class.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OacisTimeSlot(models.Model):
    _name = 'oacis.time.slot'
    _description = 'Time Slot Template'
    _inherit = ['oacis.mixin']
    _order = 'sequence, start_time'
    _check_company_auto = True

    name = fields.Char(
        string='Slot Name',
        required=True,
        tracking=True,
        help='e.g. Period 1, Morning Slot A',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    campus_id = fields.Many2one(
        comodel_name='oacis.campus',
        string='Campus',
        ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
        help='Leave empty if this slot template applies '
             'to all campuses of the institution',
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order — e.g. Period 1 before Period 2',
    )

    start_time = fields.Float(
        string='Start Time',
        required=True,
        help='Use float hours e.g. 9.0 = 9:00 AM, 14.5 = 2:30 PM',
    )

    end_time = fields.Float(
        string='End Time',
        required=True,
        help='Use float hours e.g. 10.0 = 10:00 AM',
    )

    duration_minutes = fields.Integer(
        string='Duration (Minutes)',
        compute='_compute_duration_minutes',
        store=True,
        depends=['start_time', 'end_time'],
    )

    slot_type = fields.Selection(
        string='Slot Type',
        required=True,
        default='lecture',
        selection=[
            ('lecture', 'Lecture'),
            ('lab', 'Lab Session'),
            ('break', 'Break'),
            ('lunch', 'Lunch Break'),
            ('activity', 'Activity Period'),
        ],
    )

    is_break = fields.Boolean(
        string='Is Break Period',
        compute='_compute_is_break',
        store=True,
        depends=['slot_type'],
    )

    display_label = fields.Char(
        string='Display Label',
        compute='_compute_display_label',
        store=True,
        depends=['name', 'start_time', 'end_time'],
    )

    @api.depends('start_time', 'end_time')
    def _compute_duration_minutes(self):
        for rec in self:
            if rec.end_time > rec.start_time:
                rec.duration_minutes = int(
                    (rec.end_time - rec.start_time) * 60,
                )
            else:
                rec.duration_minutes = 0

    @api.depends('slot_type')
    def _compute_is_break(self):
        for rec in self:
            rec.is_break = rec.slot_type in ('break', 'lunch')

    @api.depends('name', 'start_time', 'end_time')
    def _compute_display_label(self):
        for rec in self:
            start_str = rec._float_to_time_str(rec.start_time)
            end_str = rec._float_to_time_str(rec.end_time)
            rec.display_label = '%s (%s - %s)' % (
                rec.name, start_str, end_str,
            )

    def _float_to_time_str(self, float_hour):
        hours = int(float_hour)
        minutes = int(round((float_hour - hours) * 60))
        if minutes == 60:
            hours += 1
            minutes = 0
        period = 'AM' if hours < 12 else 'PM'
        display_hour = hours if 1 <= hours <= 12 else (
            hours - 12 if hours > 12 else 12
        )
        return '%02d:%02d %s' % (
            display_hour, minutes, period,
        )

    _sql_constraints = [
        (
            'unique_slot_name_company_campus',
            'UNIQUE(name, company_id, campus_id)',
            'A time slot with this name already exists for this campus.',
        ),
    ]

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if rec.start_time < 0 or rec.start_time >= 24:
                raise ValidationError(
                    _('Start time must be between 00:00 and 23:59.'),
                )
            if rec.end_time <= 0 or rec.end_time > 24:
                raise ValidationError(
                    _('End time must be between 00:01 and 24:00.'),
                )
            if rec.end_time <= rec.start_time:
                raise ValidationError(
                    _('End time must be after start time.'),
                )

    @api.constrains('start_time', 'end_time', 'campus_id', 'company_id')
    def _check_no_overlap_same_campus(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
            ]
            if rec.campus_id:
                domain.append(
                    ('campus_id', 'in', [rec.campus_id.id, False]),
                )
            else:
                domain.append(('campus_id', '=', False))
            others = self.search(domain)
            for other in others:
                if (rec.start_time < other.end_time
                        and rec.end_time > other.start_time):
                    raise ValidationError(
                        _('Time slot "%s" (%s-%s) overlaps with existing '
                          'slot "%s" (%s-%s).')
                        % (rec.name, rec.start_time, rec.end_time,
                           other.name, other.start_time, other.end_time),
                    )
