"""
UniCore Grade Book Config
=========================

One configuration per course offering. Holds the percentage of
continuous assessment (CA / internal) marks that assignments
contribute and orchestrates the read-only roll-up of assignment
scores into the existing ``unicore.grade.entry.internal_marks``
field.

Design constraints honoured (from the grading security audit):
- No schema change: the grade book adds no columns to
  ``unicore.grade.entry`` — it aggregates into the existing
  ``internal_marks`` field.
- Business rules stay in the grading module's ``action_*``
  methods: this module never writes ``entry_state`` and only
  pushes CA marks to entries in the editable ``draft`` /
  ``submitted`` states, within ``[0, internal_max]`` so the
  grading module's own ``_check_internal_marks`` constraint
  keeps applying.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreGradeBookConfig(models.Model):
    _name = 'unicore.gradebook.config'
    _description = 'Grade Book Configuration'
    _inherit = ['unicore.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'semester_id desc, course_id'
    _check_company_auto = True
    _rec_name = 'name'

    # ------- IDENTITY -------

    name = fields.Char(
        string='Grade Book',
        compute='_compute_name',
        store=True,
    )

    @api.depends('course_offering_id.name')
    def _compute_name(self):
        for rec in self:
            offering = rec.course_offering_id
            rec.name = 'Grade Book \u2014 %s' % (
                offering.name if offering else 'New'
            )

    # ------- OFFERING / COURSE -------

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), "
               "('offering_state', 'in', "
               "['open','ongoing','completed'])]",
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
        comodel_name='unicore.campus',
        string='Campus',
        related='course_offering_id.campus_id',
        store=True,
        readonly=True,
    )
    faculty_member_id = fields.Many2one(
        comodel_name='unicore.faculty.member',
        string='Instructor',
        related='course_offering_id.faculty_member_id',
        store=True,
        readonly=True,
        index=True,
    )

    # ------- WEIGHTING -------

    assignment_weight_pct = fields.Float(
        string='Assignment Weight (%)',
        default=20.0,
        digits=(5, 2),
        tracking=True,
        help='Percentage of the internal / CA marks that graded '
             'assignments contribute. E.g. 20 means assignments '
             'are worth 20% of the CA marks.',
    )
    max_ca_marks = fields.Float(
        string='CA Max Marks',
        related='course_id.internal_assessment_marks',
        store=True,
        readonly=True,
        digits=(6, 2),
        help='Maximum internal / CA marks defined on the course.',
    )

    # ------- ASSIGNMENTS -------

    assignment_ids = fields.One2many(
        comodel_name='unicore.assignment',
        inverse_name='course_offering_id',
        string='Assignments',
    )
    assignment_count = fields.Integer(
        string='Assignments',
        compute='_compute_stats',
        store=True,
    )
    graded_assignment_count = fields.Integer(
        string='Graded Assignments',
        compute='_compute_stats',
        store=True,
    )

    # ------- STUDENT LINES -------

    student_line_ids = fields.One2many(
        comodel_name='unicore.gradebook.student.line',
        inverse_name='config_id',
        string='Student Lines',
    )
    student_count = fields.Integer(
        string='Students',
        compute='_compute_stats',
        store=True,
    )
    class_avg_assignment_pct = fields.Float(
        string='Class Average (%)',
        compute='_compute_stats',
        store=True,
        digits=(5, 2),
    )
    synced_count = fields.Integer(
        string='Synced to Grade Entries',
        compute='_compute_stats',
        store=True,
    )
    pending_count = fields.Integer(
        string='Pending Grade Entry Sync',
        compute='_compute_stats',
        store=True,
    )
    sync_progress_pct = fields.Integer(
        string='Sync Progress (%)',
        compute='_compute_stats',
        store=True,
        help='Percentage of student lines already synced to their '
             'grade entries (0-100).',
    )

    @api.depends('assignment_ids.assignment_state',
                 'student_line_ids.assignment_percentage',
                 'student_line_ids.is_synced',
                 'student_line_ids.can_apply_ca_marks')
    def _compute_stats(self):
        for rec in self:
            rec.assignment_count = len(rec.assignment_ids)
            rec.graded_assignment_count = len(
                rec.assignment_ids.filtered(
                    lambda a: a.graded_count > 0
                )
            )
            lines = rec.student_line_ids
            rec.student_count = len(lines)
            if lines:
                rec.class_avg_assignment_pct = round(
                    sum(lines.mapped('assignment_percentage'))
                    / len(lines), 2
                )
            else:
                rec.class_avg_assignment_pct = 0.0
            rec.synced_count = len(
                lines.filtered(lambda l: l.is_synced)
            )
            rec.pending_count = len(
                lines.filtered(
                    lambda l: l.can_apply_ca_marks
                    and not l.is_synced
                )
            )
            rec.sync_progress_pct = round(
                (rec.synced_count * 100.0 / rec.student_count)
                if rec.student_count else 0.0, 0
            )

    # ------- CONSTRAINTS -------

    _check_unique_course_offering = models.Constraint(
        'UNIQUE(course_offering_id)',
        'A grade book already exists for this course offering.',
    )

    @api.constrains('assignment_weight_pct')
    def _check_weight(self):
        for rec in self:
            if (rec.assignment_weight_pct < 0
                    or rec.assignment_weight_pct > 100):
                raise ValidationError(_(
                    'Assignment weight must be between 0 and 100.'
                ))

    # ------- CREATE -------

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.course_offering_id:
                rec._compute_roll_up()
        return recs

    # ------- ROLL-UP (read-only aggregation) -------

    def _compute_roll_up(self):
        """(Re)build the grade book from live assignment submissions.

        Read-only aggregation: this reads existing graded
        submissions and refreshes the stored roll-up lines. It never
        modifies assignment, submission or grading records.
        """
        Submission = self.env['unicore.assignment.submission']
        AssignmentLine = self.env['unicore.gradebook.assignment.line']
        for rec in self:
            offering = rec.course_offering_id
            if not offering:
                continue
            enrollments = offering.enrollment_ids.filtered(
                lambda e: e.enrollment_state in
                ('registered', 'completed')
            )
            existing_lines = {
                l.enrollment_id.id: l for l in rec.student_line_ids
            }
            # Batch: one search for ALL graded submissions of the
            # offering, grouped by student (avoids an N+1 search per
            # enrollment line).
            graded_all = Submission.search([
                ('course_offering_id', '=', offering.id),
                ('state', '=', 'graded'),
            ])
            by_student = {}
            for sub in graded_all:
                by_student.setdefault(
                    sub.student_id.id, []
                ).append(sub)
            for enr in enrollments:
                line = existing_lines.get(enr.id)
                if not line:
                    line = self.env[
                        'unicore.gradebook.student.line'
                    ].create({
                        'config_id': rec.id,
                        'enrollment_id': enr.id,
                    })
                    existing_lines[enr.id] = line
                graded = by_student.get(enr.student_id.id, [])
                valid_sub_ids = {s.id for s in graded}
                # Drop stale snapshots whose source submission is no
                # longer a graded submission for this student.
                #
                # These assignment lines are purely derived snapshot
                # rows owned by this grade book (faculty intentionally
                # have no direct unlink right on them), so the roll-up
                # maintains them under sudo. This only touches our own
                # derived data — it never modifies assignment,
                # submission or grading records.
                for aline in line.assignment_line_ids:
                    if aline.submission_id.id not in valid_sub_ids:
                        aline.sudo().unlink()
                by_assign = {
                    l.assignment_id.id: l
                    for l in line.assignment_line_ids
                }
                for sub in graded:
                    aline = by_assign.get(sub.assignment_id.id)
                    if aline:
                        aline.write({
                            'submission_id': sub.id,
                            'marks_obtained': sub.marks_obtained,
                        })
                    else:
                        AssignmentLine.create({
                            'student_line_id': line.id,
                            'assignment_id': sub.assignment_id.id,
                            'submission_id': sub.id,
                            'marks_obtained': sub.marks_obtained,
                        })

    def action_regenerate(self):
        """Refresh the grade book roll-up from live submissions."""
        for rec in self:
            rec._compute_roll_up()
            rec.student_line_ids._compute_grade_entry()
            rec.message_post(
                body=_('Grade book roll-up refreshed.')
            )
        return True

    # ------- GRADE ENTRY INTEGRATION (unicore.grading) -------

    def action_apply_ca_marks(self):
        """Push the computed assignment component into the existing
        internal / CA marks of each linked grade entry.

        Business rules are NOT bypassed:
        - Only entries in the editable ``draft`` / ``submitted``
          states are written.
        - ``entry_state`` is never modified — state transitions
          remain owned by the unicore_grading ``action_*`` methods.
        - Every written value stays within ``[0, internal_max]`` so
          the grading module's ``_check_internal_marks`` constraint
          keeps applying exactly as designed.
        """
        applied = 0
        skipped_locked = 0
        skipped_missing = 0
        for rec in self:
            rec._compute_roll_up()
            for line in rec.student_line_ids:
                entry = line.grade_entry_id
                if not entry:
                    skipped_missing += 1
                    continue
                if entry.entry_state not in ('draft', 'submitted'):
                    skipped_locked += 1
                    continue
                entry.write({
                    'internal_marks': line.computed_ca_component,
                })
                applied += 1
        summary = []
        if applied:
            summary.append(_('%s updated') % applied)
        if skipped_locked:
            summary.append(
                _('%s skipped (entry not editable)') % skipped_locked
            )
        if skipped_missing:
            summary.append(
                _('%s skipped (no grade entry)') % skipped_missing
            )
        for rec in self:
            rec.message_post(
                body=_('CA marks sync from grade book: %s.')
                % (', '.join(summary) or _('nothing to do'))
            )
        return True

    # ------- NAVIGATION ACTIONS -------

    def action_view_grade_entries(self):
        """Open the grade entries for the grade book's enrollments."""
        self.ensure_one()
        enroll_ids = self.student_line_ids.mapped(
            'enrollment_id'
        ).ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grade Entries'),
            'res_model': 'unicore.grade.entry',
            'view_mode': 'list,form',
            'domain': [('enrollment_id', 'in', enroll_ids)],
            'context': {
                'default_course_offering_id':
                    self.course_offering_id.id,
            },
        }

    def action_view_submissions(self):
        """Open the graded submissions feeding this grade book."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Graded Submissions'),
            'res_model': 'unicore.assignment.submission',
            'view_mode': 'list,form',
            'domain': [
                ('course_offering_id', '=',
                 self.course_offering_id.id),
                ('state', '=', 'graded'),
            ],
        }
