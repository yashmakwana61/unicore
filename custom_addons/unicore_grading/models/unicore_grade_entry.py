"""
UniCore Grade Entry Model
The core marks record for one student in one course
offering. Contains internal and external marks,
computes total, derives letter grade and grade point
from the institutional grade scale, and on finalisation
updates the linked enrollment and student records.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreGradeEntry(models.Model):
    _name = 'unicore.grade.entry'
    _description = 'Grade Entry'
    _inherit = ['unicore.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'semester_id desc, student_id'
    _check_company_auto = True
    _rec_name = 'display_name'

    # --- CORE LINKS ---

    enrollment_id = fields.Many2one(
        comodel_name='unicore.enrollment',
        string='Enrollment',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('enrollment_state','in',"
               "['registered','completed']),"
               "('company_id','=',company_id)]",
    )
    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        related='enrollment_id.student_id',
        store=True,
        readonly=True,
        index=True,
    )
    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        related='enrollment_id.course_offering_id',
        store=True,
        readonly=True,
    )
    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        related='enrollment_id.course_id',
        store=True,
        readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        related='enrollment_id.semester_id',
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='enrollment_id.company_id',
        store=True,
        readonly=True,
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('student_id', 'course_id')
    def _compute_display_name(self):
        for rec in self:
            student = rec.student_id.display_name or ''
            course = rec.course_id.code or ''
            rec.display_name = '%s \u2014 %s' % (student, course)

    # --- EXAM LINK ---

    exam_schedule_id = fields.Many2one(
        comodel_name='unicore.exam.schedule',
        string='Exam Schedule',
        ondelete='set null',
        domain="[('course_offering_id','=',"
               "course_offering_id)]",
        help='Optional link to the exam schedule',
    )

    # --- MARKS ---

    internal_marks = fields.Float(
        string='Internal / CA Marks',
        default=0.0,
        digits=(6, 2),
        tracking=True,
        help='Continuous assessment / internal marks',
    )
    internal_max = fields.Float(
        string='Internal Max Marks',
        related='course_id.internal_assessment_marks',
        store=True,
        readonly=True,
        digits=(6, 2),
    )
    external_marks = fields.Float(
        string='External / Exam Marks',
        default=0.0,
        digits=(6, 2),
        tracking=True,
        help='Final exam / external assessment marks',
    )
    external_max = fields.Float(
        string='External Max Marks',
        related='course_id.external_assessment_marks',
        store=True,
        readonly=True,
        digits=(6, 2),
    )
    total_marks_obtained = fields.Float(
        string='Total Marks Obtained',
        compute='_compute_total_marks',
        store=True,
        digits=(6, 2),
    )
    total_marks_max = fields.Float(
        string='Total Max Marks',
        related='course_id.total_marks',
        store=True,
        readonly=True,
        digits=(6, 2),
    )
    passing_marks = fields.Float(
        string='Passing Marks',
        related='course_id.passing_marks',
        store=True,
        readonly=True,
        digits=(6, 2),
    )

    @api.depends('internal_marks', 'external_marks')
    def _compute_total_marks(self):
        for rec in self:
            rec.total_marks_obtained = (
                rec.internal_marks + rec.external_marks
            )

    percentage = fields.Float(
        string='Percentage (%)',
        compute='_compute_percentage',
        store=True,
        digits=(5, 2),
    )

    @api.depends('total_marks_obtained', 'total_marks_max')
    def _compute_percentage(self):
        for rec in self:
            if rec.total_marks_max > 0:
                rec.percentage = (
                    rec.total_marks_obtained
                    / rec.total_marks_max * 100
                )
            else:
                rec.percentage = 0.0

    # --- GRADE SCALE ---

    grade_scale_id = fields.Many2one(
        comodel_name='unicore.grade.scale',
        string='Grade Scale',
        domain="[('company_id','=',company_id)]",
        help='Leave empty to use institutional default',
    )
    letter_grade = fields.Char(
        string='Letter Grade',
        compute='_compute_grade',
        store=True,
        readonly=False,
        size=5,
        tracking=True,
    )
    grade_point = fields.Float(
        string='Grade Point',
        compute='_compute_grade',
        store=True,
        readonly=False,
        digits=(4, 2),
        tracking=True,
    )
    is_pass = fields.Boolean(
        string='Passed',
        compute='_compute_grade',
        store=True,
        readonly=True,
    )
    credit_hours = fields.Float(
        string='Credit Hours',
        related='course_id.credit_hours',
        store=True,
        readonly=True,
        digits=(4, 1),
    )
    grade_points_earned = fields.Float(
        string='Grade Points Earned',
        compute='_compute_grade_points_earned',
        store=True,
        digits=(6, 3),
        help='credit_hours \u00d7 grade_point',
    )

    @api.depends('percentage', 'grade_scale_id',
                 'total_marks_obtained', 'passing_marks')
    def _compute_grade(self):
        GradeScale = self.env['unicore.grade.scale']
        for rec in self:
            scale = (
                rec.grade_scale_id
                or GradeScale.get_default_scale(
                    rec.company_id.id
                    if rec.company_id else
                    self.env.company.id
                )
            )
            if scale and rec.percentage > 0:
                letter, point = (
                    scale.get_grade_for_percentage(
                        rec.percentage
                    )
                )
                rec.letter_grade = letter
                rec.grade_point = point
                passing_line = scale.line_ids.filtered(
                    lambda l: l.letter_grade == letter
                )
                rec.is_pass = (
                    passing_line[:1].is_passing
                    if passing_line else False
                )
            elif rec.percentage == 0.0:
                rec.letter_grade = 'F'
                rec.grade_point = 0.0
                rec.is_pass = False
            else:
                rec.letter_grade = False
                rec.grade_point = 0.0
                rec.is_pass = False

    @api.depends('credit_hours', 'grade_point')
    def _compute_grade_points_earned(self):
        for rec in self:
            rec.grade_points_earned = (
                rec.credit_hours * rec.grade_point
            )

    # --- REMARKS ---

    faculty_remarks = fields.Text(
        string='Faculty Remarks',
    )
    is_supplementary_required = fields.Boolean(
        string='Supplementary Exam Required',
        default=False,
        tracking=True,
        help='Student failed and needs supplementary exam',
    )

    # --- STATUS ---

    entry_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted by Faculty'),
            ('verified', 'Verified by Registrar'),
            ('published', 'Published'),
            ('locked', 'Locked / Final'),
        ],
    )

    # --- SQL CONSTRAINTS ---

    _unique_grade_entry_enrollment = models.Constraint(
        'UNIQUE(enrollment_id)',
        'A grade entry already exists for this enrollment.',
    )

    # --- CONSTRAINTS ---

    @api.constrains('internal_marks', 'internal_max')
    def _check_internal_marks(self):
        for rec in self:
            if rec.internal_marks < 0:
                raise ValidationError(
                    _('Internal marks cannot be negative.')
                )
            if (rec.internal_max > 0
                    and rec.internal_marks > rec.internal_max):
                raise ValidationError(
                    _('Internal marks (%s) cannot exceed '
                      'maximum (%s).')
                    % (rec.internal_marks, rec.internal_max)
                )

    @api.constrains('external_marks', 'external_max')
    def _check_external_marks(self):
        for rec in self:
            if rec.external_marks < 0:
                raise ValidationError(
                    _('External marks cannot be negative.')
                )
            if (rec.external_max > 0
                    and rec.external_marks > rec.external_max):
                raise ValidationError(
                    _('External marks (%s) cannot exceed '
                      'maximum (%s).')
                    % (rec.external_marks, rec.external_max)
                )

    # --- STATE METHODS ---

    def action_submit(self):
        self.ensure_one()
        if not self.letter_grade:
            raise UserError(
                _('Please enter marks before submitting.')
            )
        self.entry_state = 'submitted'
        self.message_post(
            body=_('Grade submitted by faculty.')
        )

    def action_verify(self):
        self.ensure_one()
        self.entry_state = 'verified'
        self.message_post(
            body=_('Grade verified by registrar.')
        )

    def action_publish(self):
        """
        Publish the grade and update linked records:
        1. enrollment.grade_status \u2192 pass/fail
        2. enrollment.final_grade_letter
        3. student.total_credits_earned (if pass)
        """
        self.ensure_one()
        if self.entry_state != 'verified':
            raise UserError(
                _('Only verified grades can be published.')
            )
        self.entry_state = 'published'
        self._update_enrollment()
        self.message_post(
            body=_('Grade published. Letter: %s, '
                   'Grade Point: %s, Pass: %s')
                 % (self.letter_grade,
                    self.grade_point,
                    _('Yes') if self.is_pass else _('No'))
        )

    def action_lock(self):
        self.ensure_one()
        self.entry_state = 'locked'
        self.message_post(
            body=_('Grade locked \u2014 no further changes allowed.')
        )

    def action_reset_draft(self):
        self.ensure_one()
        if self.entry_state == 'locked':
            raise UserError(
                _('Locked grades cannot be reset. '
                  'Contact administrator.')
            )
        self.entry_state = 'draft'
        self.message_post(
            body=_('Grade reset to Draft.')
        )

    def _update_enrollment(self):
        """Update the linked enrollment record with grade result."""
        self.ensure_one()
        if not self.enrollment_id:
            return
        grade_status = 'pass' if self.is_pass else 'fail'
        self.enrollment_id.sudo().write({
            'grade_status': grade_status,
            'final_grade_letter': self.letter_grade,
            'enrollment_state': (
                'completed' if self.is_pass else 'registered'
            ),
        })
        if self.is_pass and self.credit_hours > 0:
            student = self.student_id
            new_credits = (
                student.total_credits_earned
                + int(self.credit_hours)
            )
            student.sudo().write({
                'total_credits_earned': new_credits
            })
        self._update_student_cgpa()

    def _update_student_cgpa(self):
        """
        Legacy entry point. Recompute the student's aggregated result from all
        published/locked grade entries, dispatching to the handler matching the
        institution's effective grading scheme (Phase 2).

        The default / legacy scheme is 'credit_gpa', which preserves 100% of the
        previous behavior: CGPA = sum(grade_points_earned) /
        sum(credit_hours) across all published entries for this student.
        """
        self.ensure_one()
        scheme = self.company_id._get_effective_grading_scheme()
        if scheme in ('simple_percentage', 'weighted_percentage'):
            self._update_student_result_percentage()
        elif scheme in ('pass_fail', 'rubric_standards', 'certificate_only'):
            self._update_student_result_pass_fail()
        else:
            # credit_gpa (and any unknown fallback) -> legacy CGPA path
            self._update_student_result_credit_gpa()

    def _update_student_result_credit_gpa(self):
        """
        Legacy CGPA computation (unchanged Phase 0/1 behavior).
        CGPA = sum(grade_points_earned) / sum(credit_hours) across all
        published/locked entries for this student.
        """
        self.ensure_one()
        student = self.student_id
        all_entries = self.search([
            ('student_id', '=', student.id),
            ('entry_state', 'in', ['published', 'locked']),
            ('credit_hours', '>', 0),
        ])
        if not all_entries:
            return
        total_points = sum(
            e.grade_points_earned for e in all_entries
        )
        total_credits = sum(
            e.credit_hours for e in all_entries
        )
        if total_credits > 0:
            cgpa = round(total_points / total_credits, 2)
            student.sudo().write({'cgpa': cgpa})
            _logger.info(
                'Updated CGPA for student %s: %s',
                student.student_id_number,
                cgpa,
            )

    def _update_student_result_percentage(self):
        """
        Percentage-based scheme handler (simple / weighted percentage).
        Writes the student's average percentage across all published/locked
        grade entries.
        """
        self.ensure_one()
        student = self.student_id
        all_entries = self.search([
            ('student_id', '=', student.id),
            ('entry_state', 'in', ['published', 'locked']),
        ])
        if not all_entries:
            return
        average = round(
            sum(e.percentage for e in all_entries)
            / len(all_entries), 2
        )
        student.sudo().write({'average_percentage': average})
        _logger.info(
            'Updated average percentage for student %s: %s',
            student.student_id_number,
            average,
        )

    def _update_student_result_pass_fail(self):
        """
        Pass/Fail style scheme handler (pass_fail / rubric / certificate).
        Writes the student's passed/failed course counts across all
        published/locked grade entries.
        """
        self.ensure_one()
        student = self.student_id
        all_entries = self.search([
            ('student_id', '=', student.id),
            ('entry_state', 'in', ['published', 'locked']),
        ])
        if not all_entries:
            return
        passed = sum(1 for e in all_entries if e.is_pass)
        failed = len(all_entries) - passed
        student.sudo().write({
            'courses_passed': passed,
            'courses_failed': failed,
        })
        _logger.info(
            'Updated pass/fail counts for student %s: %s / %s',
            student.student_id_number,
            passed,
            failed,
        )
