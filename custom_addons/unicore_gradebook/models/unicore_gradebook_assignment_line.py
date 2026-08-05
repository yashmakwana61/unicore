"""
UniCore Grade Book Assignment Score Line
========================================

One row per (student x assignment) capturing the graded marks
snapshot that feeds the grade book roll-up. This is a read-only
aggregation of the existing ``unicore.assignment.submission``
data — it never modifies assignment or submission records. The
source submission is kept for provenance so the score can be
traced back to the original grade.

The model is purely additive to the UniCore suite: it adds no
columns to the grading or assignment modules.
"""

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class UniCoreGradeBookAssignmentLine(models.Model):
    _name = 'unicore.gradebook.assignment.line'
    _description = 'Grade Book Assignment Score'
    _order = 'student_line_id, due_date, assignment_id'
    _check_company_auto = True
    _rec_name = 'display_name'

    # ------- RELATIONS -------

    student_line_id = fields.Many2one(
        comodel_name='unicore.gradebook.student.line',
        string='Student Line',
        required=True,
        ondelete='cascade',
        index=True,
    )
    config_id = fields.Many2one(
        comodel_name='unicore.gradebook.config',
        string='Grade Book',
        related='student_line_id.config_id',
        store=True,
        readonly=True,
        index=True,
    )
    assignment_id = fields.Many2one(
        comodel_name='unicore.assignment',
        string='Assignment',
        required=True,
        ondelete='cascade',
        index=True,
    )
    submission_id = fields.Many2one(
        comodel_name='unicore.assignment.submission',
        string='Source Submission',
        ondelete='set null',
        index=True,
        help='The graded submission this score is derived from. '
             'Kept for provenance — the grade book never edits it.',
    )
    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        related='student_line_id.student_id',
        store=True,
        readonly=True,
        index=True,
    )
    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        related='student_line_id.course_offering_id',
        store=True,
        readonly=True,
    )
    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        related='student_line_id.course_id',
        store=True,
        readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        related='student_line_id.semester_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='student_line_id.company_id',
        store=True,
        readonly=True,
    )

    # ------- SCORE SNAPSHOT -------

    assignment_title = fields.Char(
        string='Assignment',
        related='assignment_id.title',
        store=True,
        readonly=True,
    )
    assignment_type = fields.Selection(
        string='Type',
        related='assignment_id.assignment_type',
        readonly=True,
    )
    due_date = fields.Date(
        string='Due Date',
        related='assignment_id.due_date',
        readonly=True,
    )
    max_marks = fields.Float(
        string='Max Marks',
        related='assignment_id.max_marks',
        store=True,
        readonly=True,
        digits=(6, 2),
    )
    marks_obtained = fields.Float(
        string='Marks Obtained',
        digits=(6, 2),
        readonly=True,
        help='Snapshot of the graded marks at roll-up time.',
    )
    percentage = fields.Float(
        string='Score (%)',
        compute='_compute_percentage',
        store=True,
        digits=(5, 2),
    )
    is_late = fields.Boolean(
        string='Late',
        related='submission_id.is_late',
        readonly=True,
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )

    # ------- COMPUTES -------

    @api.depends('student_id', 'assignment_id')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.student_id:
                parts.append(rec.student_id.display_name)
            if rec.assignment_id:
                parts.append(rec.assignment_id.title)
            rec.display_name = (
                ' / '.join(parts) if parts else 'Score'
            )

    @api.depends('marks_obtained', 'max_marks')
    def _compute_percentage(self):
        for rec in self:
            rec.percentage = (
                rec.marks_obtained * 100.0 / rec.max_marks
                if rec.max_marks else 0.0
            )

    # ------- CONSTRAINTS -------

    _sql_constraints = [
        (
            'unique_student_assignment_line',
            'UNIQUE(student_line_id, assignment_id)',
            'A score already exists for this student and '
            'assignment in the grade book.',
        ),
    ]
