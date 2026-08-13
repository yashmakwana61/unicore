"""
Oacis Grade Book Student Line
===============================

One row per enrolled student in a grade book. Aggregates the
student's graded assignment scores and computes the weighted
contribution toward the continuous assessment (CA / internal)
marks of the linked ``oacis.grade.entry``.

Roll-up formula
---------------
    assignment_percentage = sum(marks_obtained) / sum(max_marks) * 100
                           over the student's graded submissions
    computed_ca_component = max_ca_marks
                            * (assignment_weight_pct / 100)
                            * (assignment_percentage / 100)

The component is capped at ``max_ca_marks`` so every value that is
offered to the grading module stays within its own constraint
(``internal_marks`` in ``[0, internal_max]``).

Integration safety
------------------
This model only *reads* existing grading data. Pushing the computed
component into ``internal_marks`` is done by the grade book config
action, which restricts writes to grade entries in the editable
``draft`` / ``submitted`` states and never touches ``entry_state``.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OacisGradeBookStudentLine(models.Model):
    _name = 'oacis.gradebook.student.line'
    _description = 'Grade Book Student Line'
    _order = 'student_id, id'
    _check_company_auto = True
    _rec_name = 'student_id'

    # ------- RELATIONS -------

    config_id = fields.Many2one(
        comodel_name='oacis.gradebook.config',
        string='Grade Book',
        required=True,
        ondelete='cascade',
        index=True,
    )
    course_offering_id = fields.Many2one(
        comodel_name='oacis.course.offering',
        string='Course Offering',
        related='config_id.course_offering_id',
        store=True,
        readonly=True,
        index=True,
    )
    course_id = fields.Many2one(
        comodel_name='oacis.course',
        string='Course',
        related='config_id.course_id',
        store=True,
        readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='oacis.semester',
        string='Semester',
        related='config_id.semester_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='config_id.company_id',
        store=True,
        readonly=True,
    )
    enrollment_id = fields.Many2one(
        comodel_name='oacis.enrollment',
        string='Enrollment',
        required=True,
        ondelete='cascade',
        index=True,
    )
    student_id = fields.Many2one(
        comodel_name='oacis.student',
        string='Student',
        related='enrollment_id.student_id',
        store=True,
        readonly=True,
        index=True,
    )
    assignment_line_ids = fields.One2many(
        comodel_name='oacis.gradebook.assignment.line',
        inverse_name='student_line_id',
        string='Assignment Scores',
    )

    # ------- ROLL-UP -------

    graded_assignment_count = fields.Integer(
        string='Graded Assignments',
        compute='_compute_rollup',
        store=True,
    )
    total_possible_marks = fields.Float(
        string='Total Possible Marks',
        compute='_compute_rollup',
        store=True,
        digits=(6, 2),
    )
    total_obtained_marks = fields.Float(
        string='Total Obtained Marks',
        compute='_compute_rollup',
        store=True,
        digits=(6, 2),
    )
    assignment_percentage = fields.Float(
        string='Assignment Score (%)',
        compute='_compute_rollup',
        store=True,
        digits=(5, 2),
    )

    # ------- WEIGHTED CA COMPONENT -------

    max_ca_marks = fields.Float(
        string='CA Max Marks',
        related='config_id.max_ca_marks',
        store=True,
        readonly=True,
        digits=(6, 2),
    )
    assignment_weight_pct = fields.Float(
        string='Assignment Weight (%)',
        related='config_id.assignment_weight_pct',
        store=True,
        readonly=True,
        digits=(5, 2),
    )
    computed_ca_component = fields.Float(
        string='CA Marks from Assignments',
        compute='_compute_rollup',
        store=True,
        digits=(6, 2),
        help='Weighted assignment marks scaled against the CA '
             'maximum. This is the value the grade book proposes '
             'for the grade entry internal / CA marks.',
    )

    # ------- GRADE ENTRY LINKAGE (oacis.grading) -------

    grade_entry_id = fields.Many2one(
        comodel_name='oacis.grade.entry',
        string='Grade Entry',
        compute='_compute_grade_entry',
        store=True,
        help='Linked CA / grade record for this enrollment. Read-only '
             'reference to the existing oacis.grading model.',
    )
    grade_entry_state = fields.Selection(
        string='Grade Entry Status',
        related='grade_entry_id.entry_state',
        readonly=True,
    )
    current_ca_marks = fields.Float(
        string='Current CA Marks',
        related='grade_entry_id.internal_marks',
        readonly=True,
        digits=(6, 2),
    )
    can_apply_ca_marks = fields.Boolean(
        string='Can Update CA Marks',
        compute='_compute_apply_state',
        store=True,
        help='True when a grade entry exists and is still editable '
             '(draft / submitted).',
    )
    is_synced = fields.Boolean(
        string='Synced to Grade Entry',
        compute='_compute_apply_state',
        store=True,
        help='True when the grade entry internal marks already equal '
             'the computed assignment component.',
    )

    # ------- CONSTRAINTS -------

    _check_unique_config_enrollment = models.Constraint(
        'UNIQUE(config_id, enrollment_id)',
        'This student already has a line in this grade book.',
    )

    # ------- COMPUTES -------

    @api.depends('assignment_line_ids.marks_obtained',
                 'assignment_line_ids.max_marks')
    def _compute_rollup(self):
        for rec in self:
            lines = rec.assignment_line_ids
            rec.graded_assignment_count = len(lines)
            rec.total_possible_marks = sum(
                lines.mapped('max_marks'),
            )
            rec.total_obtained_marks = sum(
                lines.mapped('marks_obtained'),
            )
            if rec.total_possible_marks:
                rec.assignment_percentage = round(
                    rec.total_obtained_marks * 100.0
                    / rec.total_possible_marks, 2,
                )
            else:
                rec.assignment_percentage = 0.0
            weight = rec.assignment_weight_pct or 0.0
            component = round(
                rec.max_ca_marks * (weight / 100.0)
                * (rec.assignment_percentage / 100.0), 2,
            )
            rec.computed_ca_component = (
                min(component, rec.max_ca_marks)
                if rec.max_ca_marks else 0.0
            )

    @api.depends('enrollment_id',
                 'enrollment_id.grade_entry_id')
    def _compute_grade_entry(self):
        """Locate the existing grade entry for each enrollment.

        Batch search so list views do not trigger N+1 queries.
        Depends on the enrollment's reverse grade_entry_ids O2m so a
        grade entry created AFTER this line is picked up without a
        manual regenerate.
        """
        if not self:
            return
        GradeEntry = self.env['oacis.grade.entry']
        enroll_ids = self.mapped('enrollment_id').ids
        entries = GradeEntry.search([
            ('enrollment_id', 'in', enroll_ids),
        ])
        by_enroll = {e.enrollment_id.id: e for e in entries}
        for rec in self:
            rec.grade_entry_id = by_enroll.get(
                rec.enrollment_id.id, False,
            )

    @api.depends('grade_entry_id.entry_state',
                 'grade_entry_id.internal_marks',
                 'computed_ca_component')
    def _compute_apply_state(self):
        for rec in self:
            entry = rec.grade_entry_id
            rec.can_apply_ca_marks = bool(
                entry and entry.entry_state in ('draft', 'submitted'),
            )
            rec.is_synced = bool(
                entry and round(entry.internal_marks or 0.0, 2)
                == round(rec.computed_ca_component or 0.0, 2),
            )

    # ------- GRADE ENTRY ACTIONS -------

    def action_apply_line(self):
        """Push this line's computed CA component into its linked
        grade entry when the entry is still editable.

        Mirrors the config-level ``action_apply_ca_marks`` business
        rules: only ``draft`` / ``submitted`` entries are written and
        ``entry_state`` is never touched.
        """
        for rec in self:
            entry = rec.grade_entry_id
            if not entry:
                raise UserError(_(
                    'No grade entry linked to %s yet.',
                ) % rec.student_id.display_name)
            if entry.entry_state not in ('draft', 'submitted'):
                raise UserError(_(
                    'The grade entry for %s is %s and can no longer '
                    'be updated from the grade book (only draft / '
                    'submitted entries are editable).',
                ) % (rec.student_id.display_name, entry.entry_state))
        for rec in self:
            rec.grade_entry_id.write({
                'internal_marks': rec.computed_ca_component,
            })
        return True

    def action_view_grade_entry(self):
        """Open the linked grade entry, if one exists."""
        self.ensure_one()
        if not self.grade_entry_id:
            raise UserError(_(
                'No grade entry linked to this student yet.',
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grade Entry'),
            'res_model': 'oacis.grade.entry',
            'view_mode': 'form',
            'res_id': self.grade_entry_id.id,
        }
