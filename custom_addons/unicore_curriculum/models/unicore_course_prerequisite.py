"""
UniCore Course Prerequisite Model
Defines prerequisite relationships between courses.
A prerequisite is a course that must be completed
before a student can enroll in another course.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreCoursePrerequisite(models.Model):
    _name = 'unicore.course.prerequisite'
    _description = 'Course Prerequisite'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['course_id.display_name', 'prerequisite_course_id.display_name'],
    )

    @api.depends('course_id.display_name', 'prerequisite_course_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            course_name = (
                rec.course_id.display_name if rec.course_id else ''
            )
            prereq_name = (
                rec.prerequisite_course_id.display_name
                if rec.prerequisite_course_id else ''
            )
            rec.display_name = '%s -> %s' % (course_name, prereq_name)
    _order = 'course_id, prerequisite_course_id'

    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        required=True,
        ondelete='cascade',
        index=True
    )
    prerequisite_course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Prerequisite Course',
        required=True,
        ondelete='restrict',
        index=True,
        help='This course must be completed before enrolling in the parent course'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='course_id.company_id',
        store=True,
        readonly=True
    )
    prerequisite_type = fields.Selection(
        selection=[
            ('mandatory', 'Mandatory'),
            ('recommended', 'Recommended'),
            ('co_requisite', 'Co-Requisite'),
        ],
        string='Prerequisite Type',
        required=True,
        default='mandatory',
        help='Mandatory: must pass before enrolling. '
             'Recommended: advised but not enforced. '
             'Co-Requisite: must be taken simultaneously.'
    )
    minimum_grade = fields.Char(
        string='Minimum Grade Required',
        help='e.g. C, 50%, Pass — leave empty for any pass'
    )
    notes = fields.Text(
        string='Notes'
    )

    # ------- SQL CONSTRAINTS -------

    _sql_constraints = [
        (
            'unique_course_prerequisite',
            'UNIQUE(course_id, prerequisite_course_id)',
            'This prerequisite is already defined for this course.',
        ),
    ]

    # ------- CONSTRAINTS -------

    @api.constrains('course_id', 'prerequisite_course_id')
    def _check_no_self_prerequisite(self):
        for rec in self:
            if rec.course_id == rec.prerequisite_course_id:
                raise ValidationError(
                    _('A course cannot be its own prerequisite.')
                )

    @api.constrains('course_id', 'prerequisite_course_id')
    def _check_no_circular_prerequisite(self):
        for rec in self:
            if self._has_circular_dependency(
                rec.course_id,
                rec.prerequisite_course_id
            ):
                raise ValidationError(
                    _('Circular prerequisite detected. '
                      'Course "%s" is already a prerequisite '
                      'of "%s".')
                    % (rec.course_id.name,
                       rec.prerequisite_course_id.name)
                )

    def _has_circular_dependency(self, target_course, check_course):
        """
        Recursively check if target_course appears as a
        prerequisite of check_course (i.e. circular chain).
        Returns True if circular dependency exists.
        """
        prerequisites = self.search([
            ('course_id', '=', check_course.id),
        ])
        for prereq in prerequisites:
            if prereq.prerequisite_course_id == target_course:
                return True
            if self._has_circular_dependency(
                target_course,
                prereq.prerequisite_course_id
            ):
                return True
        return False
