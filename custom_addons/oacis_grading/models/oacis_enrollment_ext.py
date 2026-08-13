"""
Oacis Enrollment & Student Extensions \u2014 Grading Module
Adds grade_entry_id reverse link to oacis.enrollment
and grade-related fields/actions to oacis.student.
"""

import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class OacisEnrollmentGradingExt(models.Model):
    _inherit = 'oacis.enrollment'

    grade_entry_id = fields.One2many(
        comodel_name='oacis.grade.entry',
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


class OacisStudentGradingExt(models.Model):
    _inherit = 'oacis.student'

    grade_entry_count_student = fields.Integer(
        string='Grade Entries',
        compute='_compute_grade_entry_count_student',
        store=False,
    )
    enrollment_ids_for_grades = fields.One2many(
        comodel_name='oacis.enrollment',
        inverse_name='student_id',
        string='Enrollments',
        readonly=True,
    )
    average_percentage = fields.Float(
        string='Average Percentage',
        default=0.0,
        digits=(5, 2),
        help='Average of obtained percentages across published grade entries '
             '(simple / weighted percentage grading schemes, Phase 2).',
    )
    courses_passed = fields.Integer(
        string='Courses Passed',
        default=0,
        help='Number of passed courses across published grade entries '
             '(pass/fail style schemes, Phase 2).',
    )
    courses_failed = fields.Integer(
        string='Courses Failed',
        default=0,
        help='Number of failed courses across published grade entries '
             '(pass/fail style schemes, Phase 2).',
    )

    def _compute_grade_entry_count_student(self):
        GradeEntry = self.env['oacis.grade.entry']
        if not self:
            return
        # Batch: one search for all students instead of a per-record
        # search_count (avoids N+1 on student list views).
        entries = GradeEntry.search([
            ('student_id', 'in', self.ids),
        ])
        count_by_student = {}
        for entry in entries:
            sid = entry.student_id.id
            count_by_student[sid] = count_by_student.get(sid, 0) + 1
        for rec in self:
            rec.grade_entry_count_student = count_by_student.get(
                rec.id, 0,
            )

    def action_view_grade_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grade Entries'),
            'res_model': 'oacis.grade.entry',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {
                'default_student_id': self.id,
            },
        }
