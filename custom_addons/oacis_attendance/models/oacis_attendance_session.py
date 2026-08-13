"""
UniCore Attendance Session Model
Represents one actual class session that took place
(or is scheduled to take place) on a specific date.
Sessions are generated from unicore.timetable.entry
records by the Generate Sessions wizard, with holiday
dates automatically excluded.
Faculty open a session, mark attendance for enrolled
students, then close it. Once closed a session's
attendance records are locked.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UniCoreAttendanceSession(models.Model):
    _name = 'unicore.attendance.session'
    _description = 'Attendance Session'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'session_date desc, timetable_entry_id'
    _rec_name = 'display_name'
    _check_company_auto = True

    timetable_entry_id = fields.Many2one(
        comodel_name='unicore.timetable.entry',
        string='Timetable Entry',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        related='timetable_entry_id.course_offering_id',
        store=True,
        readonly=True,
        index=True,
    )

    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        related='timetable_entry_id.course_id',
        store=True,
        readonly=True,
    )

    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        related='timetable_entry_id.semester_id',
        store=True,
        readonly=True,
    )

    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        related='timetable_entry_id.campus_id',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='timetable_entry_id.company_id',
        store=True,
        readonly=True,
    )

    room_id = fields.Many2one(
        comodel_name='unicore.room',
        string='Room',
        related='timetable_entry_id.room_id',
        store=True,
        readonly=True,
    )

    instructor_id = fields.Many2one(
        comodel_name='unicore.faculty.member',
        string='Instructor',
        related='timetable_entry_id.instructor_id',
        store=True,
        readonly=True,
    )

    time_slot_id = fields.Many2one(
        comodel_name='unicore.time.slot',
        string='Time Slot',
        related='timetable_entry_id.time_slot_id',
        store=True,
        readonly=True,
    )

    session_date = fields.Date(
        string='Session Date',
        required=True,
        tracking=True,
        index=True,
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['timetable_entry_id.display_name', 'session_date'],
    )

    day_of_week = fields.Selection(
        string='Day',
        compute='_compute_day_of_week',
        store=True,
        depends=['session_date'],
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

    is_holiday = fields.Boolean(
        string='Is Holiday',
        default=False,
        tracking=True,
        help='Mark True if this session falls on a holiday and should not count in attendance',
    )

    is_cancelled = fields.Boolean(
        string='Session Cancelled',
        default=False,
        tracking=True,
        help='Mark True if this session was cancelled (e.g. faculty sick leave, power outage)',
    )

    cancellation_reason = fields.Text(
        string='Cancellation Reason',
    )

    attendance_record_ids = fields.One2many(
        comodel_name='unicore.attendance.record',
        inverse_name='session_id',
        string='Attendance Records',
    )

    total_students = fields.Integer(
        string='Total Students',
        compute='_compute_attendance_stats',
        store=True,
        depends=['attendance_record_ids'],
    )

    present_count = fields.Integer(
        string='Present',
        compute='_compute_attendance_stats',
        store=True,
        depends=['attendance_record_ids', 'attendance_record_ids.status'],
    )

    absent_count = fields.Integer(
        string='Absent',
        compute='_compute_attendance_stats',
        store=True,
        depends=['attendance_record_ids', 'attendance_record_ids.status'],
    )

    late_count = fields.Integer(
        string='Late',
        compute='_compute_attendance_stats',
        store=True,
        depends=['attendance_record_ids', 'attendance_record_ids.status'],
    )

    excused_count = fields.Integer(
        string='Excused',
        compute='_compute_attendance_stats',
        store=True,
        depends=['attendance_record_ids', 'attendance_record_ids.status'],
    )

    attendance_percentage = fields.Float(
        string='Attendance %',
        compute='_compute_attendance_stats',
        store=True,
        digits=(5, 2),
        depends=['attendance_record_ids', 'attendance_record_ids.status'],
    )

    session_state = fields.Selection(
        string='Session Status',
        required=True,
        default='scheduled',
        tracking=True,
        selection=[
            ('scheduled', 'Scheduled'),
            ('open', 'Open for Marking'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
    )

    marked_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Attendance Marked By',
        readonly=True,
    )

    marked_on = fields.Datetime(
        string='Attendance Marked On',
        readonly=True,
    )

    _unique_session_entry_date = models.Constraint(
        'UNIQUE(timetable_entry_id, session_date)',
        'A session already exists for this timetable entry on this date.',
    )

    @api.depends('session_date')
    def _compute_day_of_week(self):
        for rec in self:
            if rec.session_date:
                rec.day_of_week = str(rec.session_date.weekday())
            else:
                rec.day_of_week = False

    @api.depends('timetable_entry_id.display_name', 'session_date')
    def _compute_display_name(self):
        for rec in self:
            entry_name = (
                rec.timetable_entry_id.display_name
                if rec.timetable_entry_id else ''
            )
            if rec.session_date:
                rec.display_name = '%s - %s' % (
                    entry_name,
                    rec.session_date.strftime('%d %b %Y'),
                )
            else:
                rec.display_name = entry_name

    @api.depends('attendance_record_ids', 'attendance_record_ids.status')
    def _compute_attendance_stats(self):
        for rec in self:
            records = rec.attendance_record_ids
            total = len(records)
            rec.total_students = total
            if total == 0:
                rec.present_count = 0
                rec.absent_count = 0
                rec.late_count = 0
                rec.excused_count = 0
                rec.attendance_percentage = 0.0
                continue
            present = len(records.filtered(lambda r: r.status == 'present'))
            absent = len(records.filtered(lambda r: r.status == 'absent'))
            late = len(records.filtered(lambda r: r.status == 'late'))
            excused = len(records.filtered(lambda r: r.status == 'excused'))
            rec.present_count = present
            rec.absent_count = absent
            rec.late_count = late
            rec.excused_count = excused
            effective_present = present + late
            rec.attendance_percentage = (
                effective_present / total * 100 if total > 0 else 0.0
            )

    @api.constrains('session_date', 'timetable_entry_id')
    def _check_session_date_in_range(self):
        for rec in self:
            entry = rec.timetable_entry_id
            if entry.effective_date_start and entry.effective_date_end:
                if not (entry.effective_date_start <= rec.session_date <= entry.effective_date_end):
                    raise ValidationError(
                        _('Session date %s is outside the timetable entry\'s active range (%s to %s).')
                        % (rec.session_date, entry.effective_date_start, entry.effective_date_end),
                    )

    def action_open_for_marking(self):
        """
        Open session for attendance marking.
        Creates one attendance record per currently
        active enrolled student for this offering.
        Only creates records for students not already
        having a record for this session.
        """
        self.ensure_one()
        if self.session_state != 'scheduled':
            raise UserError(
                _('Only scheduled sessions can be opened for marking.'),
            )
        if self.is_cancelled or self.is_holiday:
            raise UserError(
                _('Cannot open a cancelled or holiday session for attendance marking.'),
            )

        Enrollment = self.env['unicore.enrollment']
        AttendanceRecord = self.env['unicore.attendance.record']

        active_enrollments = Enrollment.search([
            ('course_offering_id', '=', self.course_offering_id.id),
            ('enrollment_state', '=', 'registered'),
        ])

        existing_student_ids = self.attendance_record_ids.mapped('student_id').ids

        records_to_create = []
        for enrollment in active_enrollments:
            if enrollment.student_id.id not in existing_student_ids:
                records_to_create.append({
                    'session_id': self.id,
                    'student_id': enrollment.student_id.id,
                    'enrollment_id': enrollment.id,
                    'status': 'absent',
                })

        if records_to_create:
            AttendanceRecord.create(records_to_create)

        self.session_state = 'open'
        self.message_post(
            body=_('Session opened for attendance marking. %d student records created.')
            % len(records_to_create),
        )

    def action_close_session(self):
        """
        Close the session and lock attendance records.
        After closing no attendance records can be
        changed without reopening (admin only).
        Also triggers attendance percentage recompute
        on all enrolled students for this offering.
        """
        self.ensure_one()
        if self.session_state != 'open':
            raise UserError(
                _('Only open sessions can be closed.'),
            )
        self.write({
            'session_state': 'closed',
            'marked_by_id': self.env.uid,
            'marked_on': fields.Datetime.now(),
        })
        self.message_post(
            body=_('Session closed. Present: %d, Absent: %d, Late: %d, Excused: %d.')
            % (self.present_count, self.absent_count, self.late_count, self.excused_count),
        )
        self.attendance_record_ids._recompute_student_stats()

    def action_reopen_session(self):
        """Reopen a closed session for correction."""
        self.ensure_one()
        self.session_state = 'open'
        self.message_post(
            body=_('Session reopened for correction by %s.') % self.env.user.name,
        )

    def action_cancel_session(self):
        """Mark session as cancelled."""
        self.ensure_one()
        if not self.cancellation_reason:
            raise UserError(
                _('Please provide a cancellation reason.'),
            )
        self.write({
            'session_state': 'cancelled',
            'is_cancelled': True,
        })
        self.message_post(
            body=_('Session cancelled. Reason: %s') % self.cancellation_reason,
        )
