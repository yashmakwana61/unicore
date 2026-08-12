"""
UniCore Course Offering Extension — Enrollment Module
Converts the static enrolled_count field from
unicore_curriculum into a live computed field driven
by actual confirmed unicore.enrollment records.
Also adds the reverse relation to enrollments and
waitlist entries.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class UniCoreCourseOfferingEnrollmentExt(models.Model):
    _inherit = 'unicore.course.offering'

    enrollment_ids = fields.One2many(
        comodel_name='unicore.enrollment',
        inverse_name='course_offering_id',
        string='Enrollments',
    )

    waitlist_ids = fields.One2many(
        comodel_name='unicore.enrollment.waitlist',
        inverse_name='course_offering_id',
        string='Waitlist',
    )

    waitlist_count = fields.Integer(
        string='Waitlisted Students',
        compute='_compute_waitlist_count',
        store=False,
    )

    enrolled_count = fields.Integer(
        string='Enrolled Students',
        compute='_compute_enrolled_count',
        store=True,
        depends=['enrollment_ids',
                 'enrollment_ids.enrollment_state'],
    )

    @api.depends('waitlist_ids', 'waitlist_ids.waitlist_state')
    def _compute_waitlist_count(self):
        for rec in self:
            rec.waitlist_count = len(
                rec.waitlist_ids.filtered(
                    lambda w: w.waitlist_state == 'waiting',
                ),
            )

    @api.depends('enrollment_ids', 'enrollment_ids.enrollment_state')
    def _compute_enrolled_count(self):
        for rec in self:
            rec.enrolled_count = len(
                rec.enrollment_ids.filtered(
                    lambda e: e.enrollment_state in
                    ('registered', 'completed'),
                ),
            )

    def action_view_enrollments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enrollments'),
            'res_model': 'unicore.enrollment',
            'view_mode': 'list,form',
            'domain': [
                ('course_offering_id', '=', self.id),
            ],
            'context': {
                'default_course_offering_id': self.id,
            },
        }

    def action_view_waitlist(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Waitlist'),
            'res_model': 'unicore.enrollment.waitlist',
            'view_mode': 'list,form',
            'domain': [
                ('course_offering_id', '=', self.id),
            ],
            'context': {
                'default_course_offering_id': self.id,
            },
        }
