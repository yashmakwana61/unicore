"""
UniCore Attendance Policy Model
Defines institutional attendance requirements
per course type or per specific course offering.
Policies set the minimum attendance percentage
required for a student to be eligible for
examinations and academic progression.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UniCoreAttendancePolicy(models.Model):
    _name = 'unicore.attendance.policy'
    _description = 'Attendance Policy'
    _inherit = ['unicore.mixin']
    _order = 'company_id, sequence'
    _check_company_auto = True

    name = fields.Char(
        string='Policy Name',
        required=True,
        help='e.g. Standard 75% Policy, Lab 80% Policy',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Priority order — lower sequence = higher priority',
    )

    policy_scope = fields.Selection(
        string='Policy Scope',
        required=True,
        default='course_type',
        selection=[
            ('global', 'Global (All Courses)'),
            ('course_type', 'By Course Type'),
            ('course', 'Specific Course'),
            ('offering', 'Specific Offering'),
        ],
        help='Determines what this policy applies to',
    )

    course_type = fields.Selection(
        string='Course Type',
        selection=[
            ('theory', 'Theory'),
            ('practical', 'Practical / Lab'),
            ('theory_practical', 'Theory + Practical'),
            ('online', 'Online'),
            ('blended', 'Blended Learning'),
            ('project', 'Project Based'),
            ('seminar', 'Seminar'),
        ],
        help='Required when scope is By Course Type',
    )

    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
        help='Required when scope is Specific Course',
    )

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        ondelete='restrict',
        domain="[('company_id', '=', company_id)]",
        help='Required when scope is Specific Offering',
    )

    min_attendance_percentage = fields.Float(
        string='Minimum Attendance %',
        required=True,
        default=75.0,
        digits=(5, 2),
        help='Students below this threshold receive a shortage alert',
    )

    warning_threshold_percentage = fields.Float(
        string='Warning Threshold %',
        required=True,
        default=80.0,
        digits=(5, 2),
        help='Students below this but above minimum receive a warning',
    )

    is_exam_eligibility_linked = fields.Boolean(
        string='Linked to Exam Eligibility',
        default=True,
        help='If True students below minimum cannot sit for exams (enforced by unicore_exam)',
    )

    description = fields.Text(
        string='Policy Description',
    )

    @api.constrains('min_attendance_percentage', 'warning_threshold_percentage')
    def _check_thresholds(self):
        for rec in self:
            if not (0 < rec.min_attendance_percentage <= 100):
                raise ValidationError(
                    _('Minimum attendance percentage must be between 0 and 100.'),
                )
            if not (0 < rec.warning_threshold_percentage <= 100):
                raise ValidationError(
                    _('Warning threshold must be between 0 and 100.'),
                )
            if rec.warning_threshold_percentage < rec.min_attendance_percentage:
                raise ValidationError(
                    _('Warning threshold must be greater than or equal to minimum attendance percentage.'),
                )

    @api.constrains('policy_scope', 'course_type', 'course_id', 'course_offering_id')
    def _check_scope_fields(self):
        for rec in self:
            if rec.policy_scope == 'course_type' and not rec.course_type:
                raise ValidationError(
                    _('Course Type is required when scope is By Course Type.'),
                )
            if rec.policy_scope == 'course' and not rec.course_id:
                raise ValidationError(
                    _('Course is required when scope is Specific Course.'),
                )
            if rec.policy_scope == 'offering' and not rec.course_offering_id:
                raise ValidationError(
                    _('Course Offering is required when scope is Specific Offering.'),
                )

    @api.model
    def get_policy_for_offering(self, offering):
        """
        Returns the most specific applicable policy
        for a given course offering, following this
        priority (highest to lowest):
          1. Specific Offering match
          2. Specific Course match
          3. Course Type match
          4. Global policy
        Returns the policy with the lowest sequence
        number if multiple match at the same level.
        Returns None if no policy exists.
        """
        company_id = offering.company_id.id
        course_type = offering.course_id.course_type
        course_id = offering.course_id.id

        for scope, domain_extra in [
            ('offering', [
                ('course_offering_id', '=', offering.id),
            ]),
            ('course', [
                ('course_id', '=', course_id),
            ]),
            ('course_type', [
                ('course_type', '=', course_type),
            ]),
            ('global', []),
        ]:
            policy = self.search([
                ('company_id', '=', company_id),
                ('policy_scope', '=', scope),
                ('active', '=', True),
            ] + domain_extra, order='sequence asc', limit=1)
            if policy:
                return policy
        return self.browse()
