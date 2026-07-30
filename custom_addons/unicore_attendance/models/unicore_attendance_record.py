"""
UniCore Attendance Record Model
One student's attendance status for one class session.
Records are created in bulk when a session is opened
for marking. Faculty update the status field for
each student. Closed sessions lock their records.
Includes per-student cumulative attendance stats
computed across all sessions in the semester for
the same course offering.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreAttendanceRecord(models.Model):
    _name = 'unicore.attendance.record'
    _description = 'Student Attendance Record'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'session_id desc, student_id'
    _check_company_auto = True

    session_id = fields.Many2one(
        comodel_name='unicore.attendance.session',
        string='Session',
        required=True,
        ondelete='cascade',
        index=True,
    )

    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        required=True,
        ondelete='cascade',
        index=True,
    )

    enrollment_id = fields.Many2one(
        comodel_name='unicore.enrollment',
        string='Enrollment',
        ondelete='set null',
        help='Link to the enrollment record for this student in this course offering',
    )

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        related='session_id.course_offering_id',
        store=True,
        readonly=True,
        index=True,
    )

    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        related='session_id.course_id',
        store=True,
        readonly=True,
    )

    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        related='session_id.semester_id',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='session_id.company_id',
        store=True,
        readonly=True,
    )

    session_date = fields.Date(
        string='Session Date',
        related='session_id.session_date',
        store=True,
        readonly=True,
    )

    status = fields.Selection(
        string='Attendance Status',
        required=True,
        default='absent',
        selection=[
            ('present', 'Present'),
            ('absent', 'Absent'),
            ('late', 'Late'),
            ('excused', 'Excused'),
        ],
        tracking=True,
    )

    late_minutes = fields.Integer(
        string='Minutes Late',
        default=0,
        help='How many minutes late the student arrived (only relevant if status is Late)',
    )

    excuse_reason = fields.Text(
        string='Excuse Reason',
        help='Reason provided for excused absence',
    )

    remarks = fields.Char(
        string='Remarks',
    )

    total_sessions_held = fields.Integer(
        string='Total Sessions Held',
        compute='_compute_student_cumulative_stats',
        store=True,
        help='Count of closed sessions for this offering this semester',
    )

    sessions_present = fields.Integer(
        string='Sessions Present',
        compute='_compute_student_cumulative_stats',
        store=True,
    )

    sessions_absent = fields.Integer(
        string='Sessions Absent',
        compute='_compute_student_cumulative_stats',
        store=True,
    )

    sessions_late = fields.Integer(
        string='Sessions Late',
        compute='_compute_student_cumulative_stats',
        store=True,
    )

    sessions_excused = fields.Integer(
        string='Sessions Excused',
        compute='_compute_student_cumulative_stats',
        store=True,
    )

    cumulative_attendance_percentage = fields.Float(
        string='Attendance %',
        compute='_compute_student_cumulative_stats',
        store=True,
        digits=(5, 2),
    )

    shortage_alert = fields.Boolean(
        string='Shortage Alert',
        compute='_compute_shortage_alert',
        store=True,
        depends=['cumulative_attendance_percentage', 'course_offering_id'],
    )

    warning_alert = fields.Boolean(
        string='Warning Alert',
        compute='_compute_shortage_alert',
        store=True,
        depends=['cumulative_attendance_percentage', 'course_offering_id'],
    )

    _unique_student_session = models.Constraint(
        'UNIQUE(session_id, student_id)',
        'Duplicate attendance record for this student in this session.',
    )

    @api.depends('status', 'session_id', 'session_id.session_state', 'student_id', 'course_offering_id')
    def _compute_student_cumulative_stats(self):
        for rec in self:
            all_records = self.search([
                ('student_id', '=', rec.student_id.id),
                ('course_offering_id', '=', rec.course_offering_id.id),
                ('session_id.session_state', '=', 'closed'),
                ('session_id.is_cancelled', '=', False),
                ('session_id.is_holiday', '=', False),
            ])
            total = len(all_records)
            rec.total_sessions_held = total
            if total == 0:
                rec.sessions_present = 0
                rec.sessions_absent = 0
                rec.sessions_late = 0
                rec.sessions_excused = 0
                rec.cumulative_attendance_percentage = 0.0
                continue
            present = len(all_records.filtered(lambda r: r.status == 'present'))
            absent = len(all_records.filtered(lambda r: r.status == 'absent'))
            late = len(all_records.filtered(lambda r: r.status == 'late'))
            excused = len(all_records.filtered(lambda r: r.status == 'excused'))
            rec.sessions_present = present
            rec.sessions_absent = absent
            rec.sessions_late = late
            rec.sessions_excused = excused
            effective = present + late
            rec.cumulative_attendance_percentage = effective / total * 100

    @api.depends('cumulative_attendance_percentage', 'course_offering_id')
    def _compute_shortage_alert(self):
        Policy = self.env['unicore.attendance.policy']
        for rec in self:
            rec.shortage_alert = False
            rec.warning_alert = False
            if not rec.course_offering_id:
                continue
            policy = Policy.get_policy_for_offering(rec.course_offering_id)
            if not policy:
                continue
            pct = rec.cumulative_attendance_percentage
            if pct < policy.min_attendance_percentage:
                rec.shortage_alert = True
            elif pct < policy.warning_threshold_percentage:
                rec.warning_alert = True

    def _recompute_student_stats(self):
        """
        Manually trigger recomputation of cumulative
        stats for all unique student+offering pairs
        in this recordset. Called by
        action_close_session() after session is closed.
        """
        if not self:
            return
        self._compute_student_cumulative_stats()
        self._compute_shortage_alert()

    def write(self, vals):
        for rec in self:
            if rec.session_id.session_state == 'closed' and not self.env.context.get('force_write_closed_session'):
                raise UserError(
                    _('Cannot modify attendance records for a closed session. Reopen the session first (admin only).')
                )
        return super().write(vals)

    @api.constrains('status', 'late_minutes')
    def _check_late_minutes(self):
        for rec in self:
            if rec.status == 'late' and rec.late_minutes < 0:
                raise ValidationError(
                    _('Late minutes cannot be negative.')
                )
            if rec.status != 'late' and rec.late_minutes > 0:
                rec.late_minutes = 0
