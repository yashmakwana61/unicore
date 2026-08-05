"""
UniCore Assignment Submission Model
A submission is one student's submitted work for an assignment.
Students upload a file through the portal; submissions carry a
state (draft → submitted/late → graded/returned). Faculty grade
submissions with marks, feedback, an optional rubric evaluation
and positional annotations stored as a JSON text field.

Annotations (v1): stored as a JSON array of positional comments
against the submitted file, e.g.
[{"page": 1, "x": 120, "y": 340, "text": "Revisit this section"}]
A full PDF-markup UI is a stretch goal and not required for v1.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import json
import logging

_logger = logging.getLogger(__name__)


class UniCoreAssignmentSubmission(models.Model):
    _name = 'unicore.assignment.submission'
    _description = 'Assignment Submission'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc, id desc'
    _check_company_auto = True
    _rec_name = 'display_name'

    # ------- RELATIONS -------

    assignment_id = fields.Many2one(
        comodel_name='unicore.assignment',
        string='Assignment',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    enrollment_id = fields.Many2one(
        comodel_name='unicore.enrollment',
        string='Enrollment',
        ondelete='set null',
        index=True,
    )

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        related='assignment_id.course_offering_id',
        store=True,
        readonly=True,
    )
    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        related='assignment_id.course_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='assignment_id.company_id',
        store=True,
        readonly=True,
    )
    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        related='assignment_id.campus_id',
        store=True,
        readonly=True,
    )
    rubric_id = fields.Many2one(
        comodel_name='unicore.assignment.rubric',
        string='Rubric',
        related='assignment_id.rubric_id',
        store=True,
        readonly=True,
    )

    # ------- SUBMISSION CONTENT -------

    submission_file = fields.Binary(
        string='Submitted File',
        attachment=True,
        help='The file the student uploaded for this assignment',
    )
    submission_filename = fields.Char(
        string='File Name',
        help='Original filename of the submitted file',
    )
    submission_text = fields.Text(
        string='Submission Notes',
        help='Optional student notes accompanying the submission',
    )
    submission_date = fields.Datetime(
        string='Submission Date',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
    )
    attempt_count = fields.Integer(
        string='Attempt Count',
        default=1,
        help='How many times the student has submitted',
    )

    # ------- STATE -------

    state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('late', 'Late'),
            ('graded', 'Graded'),
            ('returned', 'Returned'),
        ],
        help='Draft: student started but not submitted. Submitted: work '
             'delivered on time. Late: delivered after the due date. '
             'Graded: marks assigned. Returned: sent back for revision.',
    )
    is_late = fields.Boolean(
        string='Late Submission',
        compute='_compute_is_late',
        store=True,
        readonly=False,
    )
    late_minutes = fields.Integer(
        string='Late By (minutes)',
        compute='_compute_is_late',
        store=True,
        readonly=False,
    )

    # ------- GRADING -------

    marks_obtained = fields.Float(
        string='Marks Obtained',
        tracking=True,
    )
    feedback = fields.Html(
        string='Feedback',
        tracking=True,
    )
    graded_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Graded By',
        readonly=True,
    )
    graded_date = fields.Datetime(
        string='Graded Date',
        readonly=True,
    )
    rubric_evaluation_ids = fields.One2many(
        comodel_name='unicore.assignment.submission.criterion',
        inverse_name='submission_id',
        string='Rubric Evaluation',
    )
    rubric_points_awarded = fields.Float(
        string='Rubric Points',
        compute='_compute_rubric_totals',
    )
    rubric_total = fields.Float(
        string='Rubric Total',
        related='rubric_id.total_points',
        readonly=True,
    )

    # ------- ANNOTATIONS (v1: JSON text) -------

    annotations = fields.Text(
        string='Annotations (JSON)',
        help='Positional comments against the submitted file '
             'stored as a JSON array. e.g. '
             '[{"page":1,"x":120,"y":340,"text":"..."}]',
    )
    annotation_count = fields.Integer(
        string='Annotation Count',
        compute='_compute_annotation_count',
    )

    # ------- DISPLAY -------

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    marks_percentage = fields.Float(
        string='Marks (%)',
        compute='_compute_percentage',
    )
    grade_letter = fields.Char(
        string='Grade',
        compute='_compute_percentage',
    )

    # ------- COMPUTES -------

    @api.depends('student_id', 'assignment_id', 'course_id')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.student_id:
                parts.append(rec.student_id.display_name)
            if rec.course_id:
                parts.append(rec.course_id.code)
            if rec.assignment_id:
                parts.append(rec.assignment_id.title)
            rec.display_name = (
                ' / '.join(parts) if parts else 'Submission'
            )

    @api.depends('submission_date', 'assignment_id.due_datetime',
                 'assignment_id.is_late_submission_allowed',
                 'assignment_id.due_date')
    def _compute_is_late(self):
        for rec in self:
            rec.is_late = False
            rec.late_minutes = 0
            due_dt = rec.assignment_id.due_datetime
            if not rec.submission_date or not due_dt:
                continue
            if rec.submission_date > due_dt:
                delta = rec.submission_date - due_dt
                rec.late_minutes = int(
                    delta.total_seconds() // 60
                )
                rec.is_late = True

    @api.depends('rubric_evaluation_ids.points_awarded')
    def _compute_rubric_totals(self):
        for rec in self:
            rec.rubric_points_awarded = sum(
                rec.rubric_evaluation_ids.mapped(
                    'points_awarded'
                )
            )

    def _compute_annotation_count(self):
        for rec in self:
            count = 0
            try:
                data = json.loads(rec.annotations or '[]')
                if isinstance(data, list):
                    count = len(data)
            except (ValueError, TypeError):
                count = 0
            rec.annotation_count = count

    @api.depends('marks_obtained', 'assignment_id.max_marks')
    def _compute_percentage(self):
        for rec in self:
            if rec.assignment_id.max_marks:
                rec.marks_percentage = round(
                    rec.marks_obtained * 100.0
                    / rec.assignment_id.max_marks, 2
                )
            else:
                rec.marks_percentage = 0.0
            pct = rec.marks_percentage
            if pct >= 90:
                rec.grade_letter = 'A'
            elif pct >= 80:
                rec.grade_letter = 'B'
            elif pct >= 70:
                rec.grade_letter = 'C'
            elif pct >= 60:
                rec.grade_letter = 'D'
            elif pct >= 50:
                rec.grade_letter = 'E'
            elif rec.state == 'graded':
                rec.grade_letter = 'F'
            else:
                rec.grade_letter = False

    # ------- CONSTRAINTS -------

    _sql_constraints = [
        (
            'unique_student_assignment',
            'UNIQUE(assignment_id, student_id)',
            'This student already has a submission for '
            'this assignment.',
        ),
    ]

    @api.constrains('marks_obtained')
    def _check_marks_obtained(self):
        for rec in self:
            if rec.marks_obtained < 0:
                raise ValidationError(_(
                    'Marks obtained cannot be negative.'
                ))
            if (rec.assignment_id.max_marks
                    and rec.marks_obtained
                    > rec.assignment_id.max_marks):
                raise ValidationError(_(
                    'Marks obtained cannot exceed the maximum '
                    'marks of the assignment.'
                ))

    # ------- SEQUENCE / DEFAULT ENROLLMENT -------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('enrollment_id'):
                student_id = vals.get('student_id')
                assignment_id = vals.get('assignment_id')
                if student_id and assignment_id:
                    assignment = self.env[
                        'unicore.assignment'
                    ].browse(assignment_id)
                    if assignment.course_offering_id:
                        enrollment = self.env[
                            'unicore.enrollment'
                        ].search([
                            ('student_id', '=', student_id),
                            ('course_offering_id', '=',
                             assignment.course_offering_id.id),
                            ('enrollment_state', '=', 'registered'),
                        ], limit=1)
                        if enrollment:
                            vals['enrollment_id'] = enrollment.id
        return super().create(vals_list)

    # ------- ACTIONS -------

    def action_submit(self):
        """Submit the draft submission (portal / internal)."""
        for rec in self:
            if rec.state in ('graded', 'returned'):
                raise UserError(_(
                    'This submission has already been graded.'
                ))
            if not rec.submission_file and not rec.submission_text:
                raise UserError(_(
                    'Please attach a file or add notes before '
                    'submitting.'
                ))
            rec.submission_date = fields.Datetime.now()
            rec.attempt_count = rec.attempt_count + 1
            # late re-computed from submission_date
            rec._compute_is_late()
            rec.state = 'late' if rec.is_late else 'submitted'
            rec.assignment_id._notify_faculty(rec)

    def action_reset_to_draft(self):
        """Allow the student to revise a returned submission."""
        for rec in self:
            if rec.state != 'returned':
                raise UserError(_(
                    'Only returned submissions can be reset '
                    'to draft.'
                ))
            rec.state = 'draft'
            rec.feedback = False
            rec.marks_obtained = 0.0
            rec.rubric_evaluation_ids.unlink()

    def action_grade(self):
        """Mark this submission as graded by the current user."""
        for rec in self:
            if rec.state not in ('submitted', 'late', 'returned'):
                raise UserError(_(
                    'Only submitted or late submissions can '
                    'be graded.'
                ))
            rec.state = 'graded'
            rec.graded_by_id = self.env.uid
            rec.graded_date = fields.Datetime.now()
            # Notify the student of the grade
            try:
                Engine = self.env['unicore.notification.engine']
                Engine.send_to_student(
                    student=rec.student_id,
                    trigger_event='assignment_graded',
                    variables={
                        'assignment_title': (
                            rec.assignment_id.title
                        ),
                        'course_name': (
                            rec.course_id.code
                            if rec.course_id else ''
                        ),
                        'marks_obtained': str(rec.marks_obtained),
                        'max_marks': str(
                            rec.assignment_id.max_marks
                        ),
                    },
                )
            except Exception as e:
                _logger.error(
                    'Grade notification failed: %s', str(e),
                )

    def action_return(self):
        """Return the submission for revision."""
        for rec in self:
            if rec.state != 'graded':
                raise UserError(_(
                    'Only graded submissions can be returned.'
                ))
            rec.state = 'returned'

    def action_reopen(self):
        """Reopen a graded submission for regrading."""
        for rec in self:
            if rec.state != 'graded':
                raise UserError(_(
                    'Only graded submissions can be reopened.'
                ))
            rec.state = 'submitted'
            rec.graded_by_id = False
            rec.graded_date = False

    # ------- ANNOTATION HELPERS -------

    def get_annotations(self):
        """Return the annotations as a parsed Python list."""
        self.ensure_one()
        try:
            data = json.loads(self.annotations or '[]')
            return data if isinstance(data, list) else []
        except (ValueError, TypeError):
            return []

    def set_annotations(self, annotation_list):
        """Persist a list of positional comments as JSON."""
        self.ensure_one()
        if not isinstance(annotation_list, list):
            raise ValidationError(_(
                'Annotations must be a JSON list.'
            ))
        self.annotations = json.dumps(
            annotation_list, ensure_ascii=False
        )

    def add_annotation(self, page, x, y, text, **extra):
        """Append one positional comment to the annotations."""
        self.ensure_one()
        annotations = self.get_annotations()
        annotations.append(dict(
            {'page': page, 'x': x, 'y': y, 'text': text},
            **extra,
        ))
        self.set_annotations(annotations)

    def clear_annotations(self):
        """Remove all annotations from the submission."""
        self.ensure_one()
        self.annotations = False


class UniCoreAssignmentSubmissionCriterion(models.Model):
    _name = 'unicore.assignment.submission.criterion'
    _description = 'Submission Rubric Evaluation'
    _order = 'sequence, id'
    _check_company_auto = True

    submission_id = fields.Many2one(
        comodel_name='unicore.assignment.submission',
        string='Submission',
        required=True,
        ondelete='cascade',
        index=True,
    )
    assignment_id = fields.Many2one(
        comodel_name='unicore.assignment',
        string='Assignment',
        related='submission_id.assignment_id',
        store=True,
        readonly=True,
    )
    criterion_id = fields.Many2one(
        comodel_name='unicore.assignment.rubric.criterion',
        string='Criterion',
        required=True,
        ondelete='restrict',
    )
    name = fields.Char(
        string='Criterion',
        related='criterion_id.name',
        readonly=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        related='criterion_id.sequence',
        store=True,
    )
    max_points = fields.Float(
        string='Max Points',
        related='criterion_id.max_points',
        readonly=True,
    )
    points_awarded = fields.Float(
        string='Points Awarded',
        default=0.0,
    )
    comments = fields.Text(
        string='Comments',
        help='Optional comment on this criterion',
    )

    _sql_constraints = [
        (
            'check_points_awarded',
            'CHECK(points_awarded >= 0)',
            'Points awarded cannot be negative.',
        ),
    ]
