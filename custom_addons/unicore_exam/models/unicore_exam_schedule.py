"""
UniCore Exam Schedule Model
Defines a single examination event for a specific
course offering. Links the course offering to an
exam date, time, venue and duration. Multiple exam
types (midterm, final, supplementary) can exist
for the same offering. Hall tickets and seating
plans are generated from the exam schedule.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UniCoreExamSchedule(models.Model):
    _name = 'unicore.exam.schedule'
    _description = 'Exam Schedule'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'exam_date, exam_start_time'
    _check_company_auto = True

    name = fields.Char(
        string='Exam Name',
        required=True,
        tracking=True,
        help='e.g. Midterm Exam - Data Structures Fall 2025',
    )

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('company_id','=',company_id),('offering_state','in',['open','ongoing','completed'])]",
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
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    exam_type = fields.Selection(
        string='Exam Type',
        required=True,
        default='final',
        tracking=True,
        selection=[
            ('midterm', 'Midterm Exam'),
            ('final', 'Final Exam'),
            ('supplementary', 'Supplementary / Makeup'),
            ('quiz', 'Quiz'),
            ('practical', 'Practical Exam'),
            ('viva', 'Viva Voce'),
            ('assignment', 'Assignment Based'),
            ('other', 'Other'),
        ],
    )

    exam_date = fields.Date(
        string='Exam Date',
        required=True,
        tracking=True,
    )

    exam_start_time = fields.Float(
        string='Start Time',
        required=True,
        help='Use float hours: 9.0 = 9:00 AM, 14.5 = 2:30 PM',
    )

    exam_end_time = fields.Float(
        string='End Time',
        required=True,
    )

    duration_minutes = fields.Integer(
        string='Duration (Minutes)',
        compute='_compute_duration',
        store=True,
        depends=['exam_start_time', 'exam_end_time'],
    )

    venue_ids = fields.Many2many(
        comodel_name='unicore.room',
        relation='unicore_exam_schedule_room_rel',
        column1='exam_schedule_id',
        column2='room_id',
        string='Exam Venues',
        domain="[('campus_id','=',campus_id),('room_type','in',['exam_hall','classroom','lecture_hall'])]",
        help='Rooms where this exam is conducted',
    )

    total_venue_capacity = fields.Integer(
        string='Total Venue Capacity',
        compute='_compute_total_capacity',
        store=True,
        depends=['venue_ids', 'venue_ids.exam_capacity'],
    )

    invigilator_ids = fields.Many2many(
        comodel_name='unicore.faculty.member',
        relation='unicore_exam_schedule_invigilator_rel',
        column1='exam_schedule_id',
        column2='faculty_member_id',
        string='Invigilators',
    )

    chief_invigilator_id = fields.Many2one(
        comodel_name='unicore.faculty.member',
        string='Chief Invigilator',
        ondelete='set null',
        tracking=True,
    )

    total_marks = fields.Float(
        string='Total Marks',
        related='course_id.total_marks',
        store=True,
        readonly=True,
        digits=(6, 1),
    )

    passing_marks = fields.Float(
        string='Passing Marks',
        related='course_id.passing_marks',
        store=True,
        readonly=True,
        digits=(6, 1),
    )

    exam_max_marks = fields.Float(
        string='Exam Max Marks',
        required=True,
        default=60.0,
        digits=(6, 1),
        help='Maximum marks for THIS exam type. e.g. Final exam = 60, Midterm = 40',
    )

    hall_ticket_ids = fields.One2many(
        comodel_name='unicore.exam.hall.ticket',
        inverse_name='exam_schedule_id',
        string='Hall Tickets',
    )

    hall_ticket_count = fields.Integer(
        string='Total Tickets',
        compute='_compute_hall_ticket_count',
        store=True,
        depends=['hall_ticket_ids'],
    )

    eligible_count = fields.Integer(
        string='Eligible Students',
        compute='_compute_eligibility_stats',
        store=True,
        depends=['hall_ticket_ids', 'hall_ticket_ids.eligibility_status'],
    )

    ineligible_count = fields.Integer(
        string='Ineligible Students',
        compute='_compute_eligibility_stats',
        store=True,
        depends=['hall_ticket_ids', 'hall_ticket_ids.eligibility_status'],
    )

    seating_ids = fields.One2many(
        comodel_name='unicore.exam.seating',
        inverse_name='exam_schedule_id',
        string='Seating Plan',
    )

    seating_count = fields.Integer(
        string='Seating Assignments',
        compute='_compute_seating_count',
        store=True,
        depends=['seating_ids'],
    )

    exam_state = fields.Selection(
        string='Exam Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('hall_tickets_generated', 'Hall Tickets Generated'),
            ('seating_generated', 'Seating Generated'),
            ('ongoing', 'Ongoing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
    )

    instructions = fields.Html(
        string='Exam Instructions',
        help='Instructions printed on hall tickets and displayed to students',
    )

    _unique_exam_type_offering = models.Constraint(
        'UNIQUE(course_offering_id, exam_type)',
        'An exam of this type already exists for this course offering.',
    )

    @api.depends('exam_start_time', 'exam_end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.exam_end_time > rec.exam_start_time:
                rec.duration_minutes = int((rec.exam_end_time - rec.exam_start_time) * 60)
            else:
                rec.duration_minutes = 0

    @api.depends('venue_ids', 'venue_ids.exam_capacity')
    def _compute_total_capacity(self):
        for rec in self:
            rec.total_venue_capacity = sum(
                room.exam_capacity or room.capacity
                for room in rec.venue_ids
            )

    @api.depends('hall_ticket_ids')
    def _compute_hall_ticket_count(self):
        for rec in self:
            rec.hall_ticket_count = len(rec.hall_ticket_ids)

    @api.depends('hall_ticket_ids', 'hall_ticket_ids.eligibility_status')
    def _compute_eligibility_stats(self):
        for rec in self:
            tickets = rec.hall_ticket_ids
            rec.eligible_count = len(tickets.filtered(
                lambda t: t.eligibility_status == 'eligible',
            ))
            rec.ineligible_count = len(tickets.filtered(
                lambda t: t.eligibility_status == 'ineligible',
            ))

    @api.depends('seating_ids')
    def _compute_seating_count(self):
        for rec in self:
            rec.seating_count = len(rec.seating_ids)

    @api.constrains('exam_start_time', 'exam_end_time')
    def _check_exam_times(self):
        for rec in self:
            if rec.exam_end_time <= rec.exam_start_time:
                raise ValidationError(_('Exam end time must be after start time.'))

    @api.constrains('exam_date', 'semester_id')
    def _check_exam_date_in_semester(self):
        for rec in self:
            sem = rec.semester_id
            if sem and sem.exam_start and sem.exam_end:
                if not (sem.exam_start <= rec.exam_date <= sem.exam_end):
                    _logger.warning(
                        'Exam date %s for %s is outside the semester exam period (%s to %s).',
                        rec.exam_date, rec.name, sem.exam_start, sem.exam_end,
                    )

    @api.constrains('exam_max_marks', 'total_marks')
    def _check_exam_marks(self):
        for rec in self:
            if rec.exam_max_marks <= 0:
                raise ValidationError(_('Exam max marks must be positive.'))
            if rec.total_marks and rec.exam_max_marks > rec.total_marks:
                raise ValidationError(
                    _('Exam max marks (%s) cannot exceed course total marks (%s).')
                    % (rec.exam_max_marks, rec.total_marks),
                )

    def action_publish(self):
        self.ensure_one()
        if not self.venue_ids:
            raise UserError(_('Please assign at least one venue before publishing the exam schedule.'))
        self.exam_state = 'published'
        self.message_post(body=_('Exam schedule published. Students can now view exam details.'))

    def action_generate_hall_tickets(self):
        self.ensure_one()
        if self.exam_state not in ('published', 'hall_tickets_generated'):
            raise UserError(_('Exam must be Published before generating hall tickets.'))

        Enrollment = self.env['unicore.enrollment']
        AttendanceRecord = self.env['unicore.attendance.record']
        AttendancePolicy = self.env['unicore.attendance.policy']
        HallTicket = self.env['unicore.exam.hall.ticket']

        active_enrollments = Enrollment.search([
            ('course_offering_id', '=', self.course_offering_id.id),
            ('enrollment_state', '=', 'registered'),
        ])

        policy = AttendancePolicy.get_policy_for_offering(self.course_offering_id)

        created_count = 0
        for enrollment in active_enrollments:
            existing = HallTicket.search([
                ('exam_schedule_id', '=', self.id),
                ('student_id', '=', enrollment.student_id.id),
            ], limit=1)
            if existing:
                continue

            eligibility_status = 'eligible'
            eligibility_note = ''

            if policy and policy.is_exam_eligibility_linked:
                att_record = AttendanceRecord.search([
                    ('student_id', '=', enrollment.student_id.id),
                    ('course_offering_id', '=', self.course_offering_id.id),
                ], limit=1)
                if att_record:
                    pct = att_record.cumulative_attendance_percentage
                    if pct < policy.min_attendance_percentage:
                        eligibility_status = 'ineligible'
                        eligibility_note = _('Attendance %s%% is below required %s%%.') % (
                            round(pct, 1), policy.min_attendance_percentage,
                        )
                else:
                    eligibility_note = _('No attendance records found.')

            HallTicket.create({
                'exam_schedule_id': self.id,
                'student_id': enrollment.student_id.id,
                'enrollment_id': enrollment.id,
                'eligibility_status': eligibility_status,
                'eligibility_note': eligibility_note,
                'ticket_state': 'draft',
            })
            created_count += 1

        self.exam_state = 'hall_tickets_generated'
        self.message_post(
            body=_('%d hall tickets generated. Eligible: %d, Ineligible: %d.')
            % (created_count, self.eligible_count, self.ineligible_count),
        )

    def action_generate_seating(self):
        self.ensure_one()
        if self.exam_state not in ('hall_tickets_generated', 'seating_generated'):
            raise UserError(_('Hall tickets must be generated before creating seating plan.'))
        if not self.venue_ids:
            raise UserError(_('Please assign exam venues before generating seating.'))

        Seating = self.env['unicore.exam.seating']
        Seating.search([('exam_schedule_id', '=', self.id)]).unlink()

        approved_tickets = self.hall_ticket_ids.filtered(
            lambda t: t.ticket_state == 'approved' and t.eligibility_status == 'eligible',
        )
        if not approved_tickets:
            raise UserError(
                _('No approved, eligible hall tickets found. Approve eligible hall tickets before generating seating.'),
            )

        student_list = list(approved_tickets)
        student_index = 0
        seating_records = []

        for room in self.venue_ids:
            room_capacity = room.exam_capacity or room.capacity
            seat_number = 1
            while student_index < len(student_list) and seat_number <= room_capacity:
                ticket = student_list[student_index]
                seating_records.append({
                    'exam_schedule_id': self.id,
                    'hall_ticket_id': ticket.id,
                    'student_id': ticket.student_id.id,
                    'room_id': room.id,
                    'seat_number': seat_number,
                })
                student_index += 1
                seat_number += 1

        if seating_records:
            Seating.create(seating_records)

        if student_index < len(student_list):
            _logger.warning(
                '%d students could not be seated due to insufficient venue capacity.',
                len(student_list) - student_index,
            )

        self.exam_state = 'seating_generated'
        self.message_post(
            body=_('Seating plan generated for %d students across %d venue(s).')
            % (len(seating_records), len(self.venue_ids)),
        )

    def action_mark_ongoing(self):
        self.ensure_one()
        self.exam_state = 'ongoing'
        self.message_post(body=_('Exam is now in progress.'))

    def action_complete(self):
        self.ensure_one()
        self.exam_state = 'completed'
        self.message_post(body=_('Exam marked as completed.'))

    def action_cancel(self):
        self.ensure_one()
        self.exam_state = 'cancelled'
        self.message_post(body=_('Exam cancelled by %s.') % self.env.user.name)

    def action_reset_draft(self):
        self.ensure_one()
        self.exam_state = 'draft'
        self.message_post(body=_('Exam reset to Draft.'))

    def action_approve_all_eligible_tickets(self):
        self.ensure_one()
        eligible_draft = self.hall_ticket_ids.filtered(
            lambda t: (t.ticket_state == 'draft'
                       and t.eligibility_status == 'eligible'),
        )
        for ticket in eligible_draft:
            ticket.ticket_state = 'approved'
        self.message_post(
            body=_('%d eligible tickets approved.') % len(eligible_draft),
        )
