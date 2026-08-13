"""
UniCore Course Offering Extension (Assignments)
Adds assignment statistics and a navigation action to the
course offering form so faculty can jump straight into the
assignments created for a specific offering.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class UniCoreCourseOfferingAssignmentExt(models.Model):
    _inherit = 'unicore.course.offering'

    assignment_ids = fields.One2many(
        comodel_name='unicore.assignment',
        inverse_name='course_offering_id',
        string='Assignments',
    )
    assignment_count = fields.Integer(
        string='Assignments',
        compute='_compute_assignment_count',
    )
    published_assignment_count = fields.Integer(
        string='Published Assignments',
        compute='_compute_assignment_count',
    )
    open_assignment_count = fields.Integer(
        string='Open Assignments',
        compute='_compute_assignment_count',
    )
    submission_count = fields.Integer(
        string='Submissions',
        compute='_compute_submission_count',
    )

    @api.depends('assignment_ids.assignment_state')
    def _compute_assignment_count(self):
        for rec in self:
            rec.assignment_count = len(rec.assignment_ids)
            rec.published_assignment_count = len(
                rec.assignment_ids.filtered(
                    lambda a: a.assignment_state == 'published',
                ),
            )
            rec.open_assignment_count = len(
                rec.assignment_ids.filtered(
                    lambda a: a.assignment_state in
                    ('published',),
                ),
            )

    @api.depends('assignment_ids.submission_ids')
    def _compute_submission_count(self):
        for rec in self:
            rec.submission_count = sum(
                len(a.submission_ids) for a in rec.assignment_ids
            )

    def action_view_assignments(self):
        """Open the assignments for this offering."""
        self.ensure_one()
        return {
            'name': _('Assignments'),
            'type': 'ir.actions.act_window',
            'res_model': 'unicore.assignment',
            'view_mode': 'list,form,kanban',
            'domain': [('course_offering_id', '=', self.id)],
            'context': {
                'default_course_offering_id': self.id,
            },
        }

    def action_view_submissions(self):
        """Open the submissions for all assignments of this offering."""
        self.ensure_one()
        return {
            'name': _('Submissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'unicore.assignment.submission',
            'view_mode': 'list,form',
            'domain': [('course_offering_id', '=', self.id)],
        }
