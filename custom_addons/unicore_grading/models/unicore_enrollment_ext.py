"""
UniCore Enrollment & Student Extensions \u2014 Grading Module
Adds grade_entry_id reverse link to unicore.enrollment
and grade-related fields/actions to unicore.student.
"""

from odoo import fields, models, _
import logging

_logger = logging.getLogger(__name__)


class UniCoreEnrollmentGradingExt(models.Model):
    _inherit = 'unicore.enrollment'

    grade_entry_id = fields.One2many(
        comodel_name='unicore.grade.entry',
        inverse_name='enrollment_id',
        string='Grade Entry',
        readonly=True,
    )
    grade_entry_count = fields.Integer(
        string='Grade Entries',
        compute='_compute_grade_entry_count',
        store=False,
    )

    def _compute_grade_entry_count(self):
        for rec in self:
            rec.grade_entry_count = len(rec.grade_entry_id)


class UniCoreStudentGradingExt(models.Model):
    _inherit = 'unicore.student'

    grade_entry_count_student = fields.Integer(
        string='Grade Entries',
        compute='_compute_grade_entry_count_student',
        store=False,
    )
    enrollment_ids_for_grades = fields.One2many(
        comodel_name='unicore.enrollment',
        inverse_name='student_id',
        string='Enrollments',
        readonly=True,
    )

    def _compute_grade_entry_count_student(self):
        GradeEntry = self.env['unicore.grade.entry']
        for rec in self:
            rec.grade_entry_count_student = (
                GradeEntry.search_count([
                    ('student_id', '=', rec.id)
                ])
            )

    def action_view_grade_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grade Entries'),
            'res_model': 'unicore.grade.entry',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {
                'default_student_id': self.id,
            },
        }
