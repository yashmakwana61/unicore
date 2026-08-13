"""
UniCore Assignment Submission Extension — Grade Book Auto-Refresh
=================================================================

Event bridge: when a submission is graded (or its marks change), the
grade book roll-up for the affected student lines refreshes
automatically so totals / percentages / the weighted CA component
stay current without faculty having to click "Regenerate Grade Book".

Why does this live in its own module?
-------------------------------------
``unicore_assignment`` already depends on ``unicore_grading``
transitively (``assignment -> notify -> fees -> grading``), so
``unicore_grading`` can NOT depend on ``unicore_assignment`` without
creating a dependency cycle. This module sits ABOVE both and wires
the assignment submission events into the grade book roll-up.

Business rules are unchanged: the grade book still never pushes
values into ``unicore.grade.entry`` on its own — that remains a
deliberate, manual "Apply CA Marks" action in the grade book config.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class UniCoreAssignmentSubmissionExt(models.Model):
    _inherit = 'unicore.assignment.submission'

    # ------- HOOKS -------

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if any(r.state == 'graded' for r in recs):
            recs._refresh_gradebook_for_submissions()
        return recs

    def write(self, vals):
        was_graded = {r.id: r.state == 'graded' for r in self}
        res = super().write(vals)
        # Refresh when a submission became graded, or was graded and
        # its state / marks changed.
        touched = self.filtered(
            lambda r: was_graded.get(r.id) or r.state == 'graded',
        )
        if touched:
            touched._refresh_gradebook_for_submissions()
        return res

    def unlink(self):
        # Capture affected grade book lines BEFORE removing the
        # source submissions, then re-derive the roll-up (stale
        # snapshot lines are dropped by the roll-up itself).
        lines = self._get_gradebook_student_lines()
        res = super().unlink()
        if lines:
            lines.config_id._compute_roll_up()
        return res

    # ------- HELPERS -------

    def _get_gradebook_student_lines(self):
        """Grade book student lines derived from these submissions."""
        StudentLine = self.env['unicore.gradebook.student.line']
        if not self:
            return StudentLine
        student_ids = self.mapped('student_id').ids
        offering_ids = self.mapped('course_offering_id').ids
        if not student_ids or not offering_ids:
            return StudentLine
        return StudentLine.search([
            ('student_id', 'in', student_ids),
            ('course_offering_id', 'in', offering_ids),
        ])

    def _refresh_gradebook_for_submissions(self):
        """Re-roll the grade books affected by these submissions."""
        lines = self._get_gradebook_student_lines()
        if not lines:
            return
        for config in lines.config_id:
            config._compute_roll_up()
