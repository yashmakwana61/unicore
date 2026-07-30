"""
UniCore Room Booking Model
Represents a one-off, non-recurring room reservation
that exists outside the regular weekly timetable
pattern — e.g. guest lectures, makeup classes,
special events. Room bookings are checked against
both other room bookings and recurring timetable
entries to prevent double-booking.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, time, timedelta
import logging

_logger = logging.getLogger(__name__)


class UniCoreRoomBooking(models.Model):
    _name = 'unicore.room.booking'
    _description = 'Ad-Hoc Room Booking'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'booking_date, time_slot_id'
    _check_company_auto = True

    name = fields.Char(
        string='Booking Title',
        required=True,
        tracking=True,
        help='e.g. Guest Lecture - AI in Healthcare',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        required=True,
        ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
    )

    room_id = fields.Many2one(
        comodel_name='unicore.room',
        string='Room',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('campus_id', '=', campus_id)]",
    )

    booking_date = fields.Date(
        string='Booking Date',
        required=True,
        tracking=True,
    )

    day_of_week = fields.Selection(
        string='Day of Week',
        compute='_compute_day_of_week',
        store=True,
        depends=['booking_date'],
        selection=[
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
        ],
    )

    time_slot_id = fields.Many2one(
        comodel_name='unicore.time.slot',
        string='Time Slot',
        required=True,
        ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
    )

    requested_by_id = fields.Many2one(
        comodel_name='unicore.faculty.member',
        string='Requested By',
        tracking=True,
    )

    purpose = fields.Selection(
        string='Purpose',
        required=True,
        default='makeup_class',
        selection=[
            ('makeup_class', 'Makeup Class'),
            ('guest_lecture', 'Guest Lecture'),
            ('special_event', 'Special Event'),
            ('meeting', 'Meeting'),
            ('exam', 'Exam / Quiz'),
            ('workshop', 'Workshop'),
            ('other', 'Other'),
        ],
    )

    related_course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Related Course Offering',
        help='Optional: link to a course offering if '
             'this is a makeup class',
    )

    description = fields.Text(string='Description / Notes')

    booking_state = fields.Selection(
        string='Status',
        required=True,
        default='requested',
        tracking=True,
        selection=[
            ('requested', 'Requested'),
            ('approved', 'Approved'),
            ('cancelled', 'Cancelled'),
        ],
    )

    approved_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Approved By',
        readonly=True,
    )

    @api.depends('booking_date')
    def _compute_day_of_week(self):
        for rec in self:
            if rec.booking_date:
                rec.day_of_week = str(rec.booking_date.weekday())
            else:
                rec.day_of_week = False

    @api.constrains('room_id', 'booking_date',
                    'time_slot_id', 'booking_state')
    def _check_room_booking_conflicts(self):
        for rec in self:
            if rec.booking_state == 'cancelled':
                continue

            # Check against other room bookings
            other_bookings = self.search([
                ('id', '!=', rec.id),
                ('room_id', '=', rec.room_id.id),
                ('booking_date', '=', rec.booking_date),
                ('time_slot_id', '=', rec.time_slot_id.id),
                ('booking_state', '!=', 'cancelled'),
            ])
            if other_bookings:
                raise ValidationError(
                    _('Room "%s" is already booked for "%s" on %s '
                      'at this time slot.')
                    % (rec.room_id.display_name,
                       other_bookings[0].name,
                       rec.booking_date)
                )

            # Check against recurring timetable entries
            TimetableEntry = self.env['unicore.timetable.entry']
            conflicting_entries = TimetableEntry.search([
                ('room_id', '=', rec.room_id.id),
                ('day_of_week', '=', rec.day_of_week),
                ('time_slot_id', '=', rec.time_slot_id.id),
                ('entry_state', '!=', 'cancelled'),
            ])
            for entry in conflicting_entries:
                if (entry.effective_date_start
                        and entry.effective_date_end):
                    if (entry.effective_date_start
                            <= rec.booking_date
                            <= entry.effective_date_end):
                        raise ValidationError(
                            _('Room "%s" has a regular timetable class '
                              '"%s" scheduled on %s at this time slot.')
                            % (rec.room_id.display_name,
                               entry.display_name,
                               rec.booking_date)
                        )

    def action_approve(self):
        self.ensure_one()
        self.write({
            'booking_state': 'approved',
            'approved_by_id': self.env.uid,
        })
        self.message_post(
            body=_('Room booking approved by %s.')
            % self.env.user.name
        )

    def action_cancel(self):
        self.ensure_one()
        self.booking_state = 'cancelled'
        self.message_post(
            body=_('Room booking cancelled by %s.')
            % self.env.user.name
        )

    def action_reset_requested(self):
        self.ensure_one()
        self.write({
            'booking_state': 'requested',
            'approved_by_id': False,
        })
