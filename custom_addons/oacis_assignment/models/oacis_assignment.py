"""
Oacis Assignment Model
Faculty create assignments against a specific course offering.
Each assignment carries a title, description, type, maximum
marks, due date and an optional reusable rubric. Published
assignments become visible to enrolled students in the student
portal; submissions are collected in the submission model.
"""

import logging
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OacisAssignment(models.Model):
    _name = 'oacis.assignment'
    _description = 'Course Assignment'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'due_date desc, id desc'
    _check_company_auto = True
    _rec_name = 'title'

    # ------- IDENTITY -------

    name = fields.Char(
        string='Assignment Code',
        readonly=True,
        copy=False,
        help='Auto-generated assignment identifier',
        tracking=True,
    )
    title = fields.Char(
        string='Title',
        required=True,
        tracking=True,
    )
    description = fields.Html(
        string='Description',
        help='Instructions and requirements for the assignment',
    )

    # ------- TYPE & MARKS -------

    assignment_type = fields.Selection(
        string='Assignment Type',
        required=True,
        default='homework',
        tracking=True,
        selection=[
            ('homework', 'Homework'),
            ('project', 'Project'),
            ('lab', 'Lab'),
            ('quiz', 'Quiz'),
        ],
    )
    max_marks = fields.Float(
        string='Maximum Marks',
        required=True,
        default=10.0,
        tracking=True,
        help='Total marks the assignment is worth',
    )
    pass_marks = fields.Float(
        string='Pass Marks',
        default=0.0,
        help='Minimum marks required to pass this assignment',
    )

    # ------- SCHEDULING -------

    due_date = fields.Date(
        string='Due Date',
        required=True,
        tracking=True,
        help='Date by which submissions are expected',
    )
    due_time = fields.Char(
        string='Due Time',
        default='23:59',
        help='Optional cutoff time on the due date, e.g. 17:00',
    )
    due_datetime = fields.Datetime(
        string='Due Date & Time',
        compute='_compute_due_datetime',
        store=True,
        readonly=False,
    )
    is_late_submission_allowed = fields.Boolean(
        string='Allow Late Submissions',
        default=True,
        tracking=True,
    )
    late_penalty_percent = fields.Float(
        string='Late Penalty (%)',
        default=0.0,
        help='Percentage of marks deducted for late submissions',
    )

    # ------- RUBRIC -------

    rubric_id = fields.Many2one(
        comodel_name='oacis.assignment.rubric',
        string='Rubric',
        ondelete='set null',
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
        help='Optional reusable rubric used to grade submissions',
    )

    # ------- OFFERING / COURSE -------

    course_offering_id = fields.Many2one(
        comodel_name='oacis.course.offering',
        string='Course Offering',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), "
               "('offering_state', 'in', ['open','ongoing'])]",
    )
    course_id = fields.Many2one(
        comodel_name='oacis.course',
        string='Course',
        related='course_offering_id.course_id',
        store=True,
        readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='oacis.semester',
        string='Semester',
        related='course_offering_id.semester_id',
        store=True,
        readonly=True,
    )
    faculty_member_id = fields.Many2one(
        comodel_name='oacis.faculty.member',
        string='Instructor',
        related='course_offering_id.faculty_member_id',
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='course_offering_id.company_id',
        store=True,
        readonly=True,
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus',
        string='Campus',
        related='course_offering_id.campus_id',
        store=True,
        readonly=True,
    )

    # ------- FILES -------

    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='oacis_assignment_attachment_rel',
        column1='assignment_id',
        column2='attachment_id',
        string='Assignment Files',
        help='Reference files such as instructions or templates',
    )
    file_count = fields.Integer(
        string='File Count',
        compute='_compute_file_count',
    )

    # ------- STATE -------

    assignment_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('closed', 'Closed'),
        ],
        help='Draft: not visible to students. Published: students can '
             'view and submit. Closed: submissions disabled.',
    )

    # ------- SUBMISSIONS -------

    submission_ids = fields.One2many(
        comodel_name='oacis.assignment.submission',
        inverse_name='assignment_id',
        string='Submissions',
    )
    submission_count = fields.Integer(
        string='Total Submissions',
        compute='_compute_submission_stats',
    )
    submitted_count = fields.Integer(
        string='Submitted',
        compute='_compute_submission_stats',
    )
    graded_count = fields.Integer(
        string='Graded',
        compute='_compute_submission_stats',
    )
    pending_count = fields.Integer(
        string='Pending Grading',
        compute='_compute_submission_stats',
    )
    avg_marks = fields.Float(
        string='Average Marks',
        compute='_compute_submission_stats',
    )
    enrolled_count = fields.Integer(
        string='Enrolled Students',
        compute='_compute_enrolled_count',
    )
    submission_rate = fields.Float(
        string='Submission Rate (%)',
        compute='_compute_submission_stats',
    )

    # ------- COMPUTES -------

    @api.depends('due_date', 'due_time')
    def _compute_due_datetime(self):
        for rec in self:
            if rec.due_date:
                try:
                    hh, mm = (rec.due_time or '23:59').split(':')
                    due_dt = datetime.combine(
                        rec.due_date, time(int(hh), int(mm)),
                    )
                except (ValueError, TypeError):
                    due_dt = datetime.combine(
                        rec.due_date, time(23, 59),
                    )
                rec.due_datetime = due_dt
            else:
                rec.due_datetime = False

    def _compute_file_count(self):
        for rec in self:
            rec.file_count = len(rec.attachment_ids)

    @api.depends('submission_ids.state')
    def _compute_submission_stats(self):
        Submission = self.env['oacis.assignment.submission']
        for rec in self:
            subs = rec.submission_ids
            submitted = subs.filtered(
                lambda s: s.state in
                ('submitted', 'late', 'graded', 'returned'),
            )
            graded = subs.filtered(lambda s: s.state == 'graded')
            rec.submission_count = len(subs)
            rec.submitted_count = len(submitted)
            rec.graded_count = len(graded)
            rec.pending_count = len(submitted) - len(graded)
            if graded:
                rec.avg_marks = sum(
                    graded.mapped('marks_obtained'),
                ) / len(graded)
            else:
                rec.avg_marks = 0.0
            if rec.enrolled_count:
                rec.submission_rate = round(
                    rec.submitted_count * 100.0
                    / rec.enrolled_count, 2,
                )
            else:
                rec.submission_rate = 0.0

    @api.depends('course_offering_id')
    def _compute_enrolled_count(self):
        Enrollment = self.env['oacis.enrollment']
        for rec in self:
            if rec.course_offering_id:
                rec.enrolled_count = Enrollment.search_count([
                    ('course_offering_id', '=',
                     rec.course_offering_id.id),
                    ('enrollment_state', '=', 'registered'),
                ])
            else:
                rec.enrolled_count = 0

    # ------- CONSTRAINTS -------

    @api.constrains('max_marks', 'pass_marks')
    def _check_marks(self):
        for rec in self:
            if rec.max_marks <= 0:
                raise ValidationError(_(
                    'Maximum marks must be greater than zero.',
                ))
            if rec.pass_marks and rec.pass_marks > rec.max_marks:
                raise ValidationError(_(
                    'Pass marks cannot exceed maximum marks.',
                ))

    @api.constrains('late_penalty_percent')
    def _check_penalty(self):
        for rec in self:
            if rec.late_penalty_percent < 0:
                raise ValidationError(_(
                    'Late penalty percentage cannot be negative.',
                ))

    # ------- SEQUENCE -------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env[
                    'ir.sequence'
                ].next_by_code('oacis.assignment')
        return super().create(vals_list)

    # ------- STATE TRANSITIONS -------

    def action_publish(self):
        """Publish the assignment and notify enrolled students."""
        for rec in self:
            if rec.assignment_state != 'draft':
                raise UserError(_(
                    'Only draft assignments can be published.',
                ))
            rec.assignment_state = 'published'
            rec._notify_students()

    def action_close(self):
        """Close the assignment to further submissions."""
        for rec in self:
            rec.assignment_state = 'closed'

    def action_set_draft(self):
        """Reopen a closed assignment back to draft."""
        for rec in self:
            rec.assignment_state = 'draft'

    # ------- NOTIFICATIONS -------

    def _notify_students(self):
        """Send notifications to all enrolled students."""
        if not self.course_offering_id:
            return
        Engine = self.env['oacis.notification.engine']
        Enrollment = self.env['oacis.enrollment']
        enrollments = Enrollment.search([
            ('course_offering_id', '=', self.course_offering_id.id),
            ('enrollment_state', '=', 'registered'),
        ])
        for enr in enrollments:
            if not enr.student_id:
                continue
            try:
                Engine.send_to_student(
                    student=enr.student_id,
                    trigger_event='assignment_published',
                    variables={
                        'assignment_title': self.title,
                        'assignment_type': dict(
                            self._fields['assignment_type']
                            .selection,
                        ).get(self.assignment_type, ''),
                        'due_date': str(self.due_date),
                        'max_marks': str(self.max_marks),
                        'course_name': (
                            self.course_id.code
                            if self.course_id else ''
                        ),
                    },
                )
            except Exception as e:
                _logger.error(
                    'Assignment notification failed for '
                    'student %s: %s',
                    enr.student_id.id, str(e),
                )

    def _notify_faculty(self, submission):
        """Notify the instructor that a submission arrived."""
        if not self.faculty_member_id:
            return
        try:
            Engine = self.env['oacis.notification.engine']
            engine = Engine
            student = submission.student_id
            engine.send_to_faculty(
                faculty=self.faculty_member_id,
                trigger_event='assignment_submitted',
                student=student,
                variables={
                    'assignment_title': self.title,
                    'course_name': (
                        self.course_id.code
                        if self.course_id else ''
                    ),
                    'student_name': (
                        student.display_name if student else ''
                    ),
                    'submission_date': str(
                        submission.submission_date or '',
                    ),
                },
            )
        except Exception as e:
            _logger.error(
                'Faculty notification failed: %s', str(e),
            )

    # ------- ACTIONS -------

    def action_view_submissions(self):
        """Open submissions for this assignment."""
        return {
            'name': _('Submissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'oacis.assignment.submission',
            'view_mode': 'list,form',
            'domain': [('assignment_id', '=', self.id)],
            'context': {
                'default_assignment_id': self.id,
            },
        }
