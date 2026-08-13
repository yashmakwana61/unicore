"""
Oacis Student Extension (Assignments)
Adds assignment submission statistics and a navigation action
to the student form so registrars/faculty can inspect a
student's assignment submissions.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class OacisStudentAssignmentExt(models.Model):
    _inherit = 'oacis.student'

    assignment_submission_ids = fields.One2many(
        comodel_name='oacis.assignment.submission',
        inverse_name='student_id',
        string='Assignment Submissions',
    )
    assignment_submission_count = fields.Integer(
        string='Assignments Submitted',
        compute='_compute_assignment_submission_count',
    )
    pending_assignment_count = fields.Integer(
        string='Pending Assignments',
        compute='_compute_assignment_submission_count',
    )
    graded_assignment_count = fields.Integer(
        string='Graded Assignments',
        compute='_compute_assignment_submission_count',
    )

    @api.depends('assignment_submission_ids.state')
    def _compute_assignment_submission_count(self):
        for rec in self:
            subs = rec.assignment_submission_ids
            rec.assignment_submission_count = len(subs)
            rec.graded_assignment_count = len(
                subs.filtered(lambda s: s.state == 'graded'),
            )
            # Pending = active enrolled courses with a published
            # assignment that has no submission yet
            pending = 0
            Enrollment = self.env['oacis.enrollment']
            enrollments = Enrollment.search([
                ('student_id', '=', rec.id),
                ('enrollment_state', '=', 'registered'),
            ])
            assignment_ids = enrollments.mapped(
                'course_offering_id.assignment_ids',
            ).filtered(
                lambda a: a.assignment_state == 'published',
            )
            submitted_ids = set(subs.mapped('assignment_id').ids)
            for assignment in assignment_ids:
                if assignment.id not in submitted_ids:
                    pending += 1
            rec.pending_assignment_count = pending

    def action_view_assignment_submissions(self):
        """Open this student's assignment submissions."""
        self.ensure_one()
        return {
            'name': _('Assignment Submissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'oacis.assignment.submission',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
        }
