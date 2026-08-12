"""
UniCore Timetable Entry Model
Represents one recurring weekly scheduled class
session: a course offering taught on a specific
day-of-week in a specific time slot, room, and by
a specific instructor, recurring across a date range
within a semester.

Implements three-dimensional conflict detection:
room conflicts, instructor conflicts, and
offering/section conflicts.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UniCoreTimetableEntry(models.Model):
    _name = 'unicore.timetable.entry'
    _description = 'Timetable Entry'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'day_of_week, time_slot_id'
    _check_company_auto = True

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), "
               "('offering_state', 'in', ['draft','open','ongoing'])]",
    )

    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        related='course_offering_id.course_id',
        store=True,
        readonly=True,
    )

    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        related='course_offering_id.semester_id',
        store=True,
        readonly=True,
    )

    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        related='course_offering_id.campus_id',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='course_offering_id.company_id',
        store=True,
        readonly=True,
    )

    day_of_week = fields.Selection(
        string='Day of Week',
        required=True,
        tracking=True,
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
        tracking=True,
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

    instructor_id = fields.Many2one(
        comodel_name='unicore.faculty.member',
        string='Instructor',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='The instructor teaching this specific timetable entry '
             '(may differ from offering primary instructor for '
             'co-taught sessions)',
    )

    date_start = fields.Date(
        string='Effective From',
        compute='_compute_date_range',
        store=True,
        depends=['course_offering_id',
                 'course_offering_id.semester_id'],
    )

    date_end = fields.Date(
        string='Effective Until',
        compute='_compute_date_range',
        store=True,
        depends=['course_offering_id',
                 'course_offering_id.semester_id'],
    )

    override_date_start = fields.Date(
        string='Custom Start Date (Override)',
        help='Leave empty to use semester start date. '
             'Set this only if this entry starts later '
             'than the semester (e.g. added mid-term).',
    )

    override_date_end = fields.Date(
        string='Custom End Date (Override)',
        help='Leave empty to use semester end date.',
    )

    effective_date_start = fields.Date(
        string='Actual Start Date',
        compute='_compute_effective_dates',
        store=True,
        depends=['date_start', 'override_date_start'],
    )

    effective_date_end = fields.Date(
        string='Actual End Date',
        compute='_compute_effective_dates',
        store=True,
        depends=['date_end', 'override_date_end'],
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['course_id', 'day_of_week', 'time_slot_id', 'room_id'],
    )

    entry_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
    )

    notes = fields.Text(string='Notes')

    @api.depends('course_offering_id',
                 'course_offering_id.semester_id')
    def _compute_date_range(self):
        for rec in self:
            sem = rec.course_offering_id.semester_id
            rec.date_start = sem.date_start if sem else False
            rec.date_end = sem.date_end if sem else False

    @api.depends('date_start', 'override_date_start',
                 'date_end', 'override_date_end')
    def _compute_effective_dates(self):
        for rec in self:
            rec.effective_date_start = (
                rec.override_date_start or rec.date_start
            )
            rec.effective_date_end = (
                rec.override_date_end or rec.date_end
            )

    @api.depends('course_id', 'day_of_week',
                 'time_slot_id', 'room_id')
    def _compute_display_name(self):
        day_labels = dict(self._fields['day_of_week'].selection)
        for rec in self:
            day_label = day_labels.get(rec.day_of_week, '')
            course_code = (
                rec.course_id.code if rec.course_id else ''
            )
            slot_name = (
                rec.time_slot_id.name if rec.time_slot_id else ''
            )
            room_code = rec.room_id.code if rec.room_id else ''
            rec.display_name = '%s - %s - %s - %s' % (
                course_code, day_label, slot_name, room_code,
            )

    _sql_constraints = [
        (
            'unique_offering_day_slot',
            'UNIQUE(course_offering_id, day_of_week, time_slot_id)',
            'This course offering already has an entry '
            'at this day and time slot.',
        ),
    ]

    def _date_ranges_overlap(self, start1, end1, start2, end2):
        """Returns True if two date ranges overlap."""
        if not all([start1, end1, start2, end2]):
            return True
        return start1 <= end2 and start2 <= end1

    @api.constrains('day_of_week', 'time_slot_id', 'room_id',
                    'instructor_id', 'effective_date_start',
                    'effective_date_end', 'entry_state')
    def _check_scheduling_conflicts(self):
        for rec in self:
            if rec.entry_state == 'cancelled':
                continue

            domain_base = [
                ('id', '!=', rec.id),
                ('day_of_week', '=', rec.day_of_week),
                ('time_slot_id', '=', rec.time_slot_id.id),
                ('entry_state', '!=', 'cancelled'),
            ]

            # CHECK 1: ROOM CONFLICT
            room_conflicts = self.search(domain_base + [
                ('room_id', '=', rec.room_id.id),
            ])
            for other in room_conflicts:
                if rec._date_ranges_overlap(
                    rec.effective_date_start,
                    rec.effective_date_end,
                    other.effective_date_start,
                    other.effective_date_end,
                ):
                    raise ValidationError(
                        _('Room Conflict: "%s" is already booked for '
                          '"%s" at this day and time slot (%s).')
                        % (rec.room_id.display_name,
                           other.display_name,
                           rec.time_slot_id.name),
                    )

            # CHECK 2: INSTRUCTOR CONFLICT
            instructor_conflicts = self.search(domain_base + [
                ('instructor_id', '=', rec.instructor_id.id),
            ])
            for other in instructor_conflicts:
                if rec._date_ranges_overlap(
                    rec.effective_date_start,
                    rec.effective_date_end,
                    other.effective_date_start,
                    other.effective_date_end,
                ):
                    raise ValidationError(
                        _('Instructor Conflict: "%s" is already scheduled '
                          'to teach "%s" at this day and time slot (%s).')
                        % (rec.instructor_id.display_name,
                           other.display_name,
                           rec.time_slot_id.name),
                    )

            # CHECK 3: SECTION/OFFERING CONFLICT
            section_conflicts = self.search(domain_base + [
                ('course_offering_id', '=', rec.course_offering_id.id),
            ])
            for other in section_conflicts:
                if rec._date_ranges_overlap(
                    rec.effective_date_start,
                    rec.effective_date_end,
                    other.effective_date_start,
                    other.effective_date_end,
                ):
                    raise ValidationError(
                        _('Section Conflict: Course offering "%s" already '
                          'has another class scheduled at this day and '
                          'time slot.')
                        % rec.course_offering_id.display_name,
                    )

    @api.constrains('day_of_week', 'time_slot_id', 'room_id',
                    'effective_date_start', 'effective_date_end',
                    'entry_state')
    def _check_against_room_bookings(self):
        RoomBooking = self.env['unicore.room.booking']
        for rec in self:
            if rec.entry_state == 'cancelled':
                continue
            conflicting_bookings = RoomBooking.search([
                ('room_id', '=', rec.room_id.id),
                ('day_of_week', '=', rec.day_of_week),
                ('time_slot_id', '=', rec.time_slot_id.id),
                ('booking_state', '!=', 'cancelled'),
            ])
            for booking in conflicting_bookings:
                if rec._date_ranges_overlap(
                    rec.effective_date_start,
                    rec.effective_date_end,
                    booking.booking_date,
                    booking.booking_date,
                ):
                    raise ValidationError(
                        _('Room Conflict: "%s" has a special booking '
                          '"%s" on %s at this time slot that conflicts '
                          'with this recurring timetable entry.')
                        % (rec.room_id.display_name,
                           booking.name,
                           booking.booking_date),
                    )

    def action_confirm(self):
        self.ensure_one()
        if not all([self.room_id, self.instructor_id, self.time_slot_id]):
            raise UserError(
                _('Room, Instructor and Time Slot must all be set '
                  'before confirming.'),
            )
        self.entry_state = 'confirmed'
        self.message_post(
            body=_('Timetable entry confirmed.'),
        )

    def action_cancel(self):
        self.ensure_one()
        self.entry_state = 'cancelled'
        self.message_post(
            body=_('Timetable entry cancelled by %s.')
            % self.env.user.name,
        )

    def action_reset_draft(self):
        self.ensure_one()
        self.entry_state = 'draft'
        self.message_post(
            body=_('Timetable entry reset to Draft.'),
        )
