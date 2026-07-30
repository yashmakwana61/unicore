"""
UniCore Semester Result Model
Per-student per-semester academic result summary.
Generated after all grade entries for a semester
are finalised. Stores semester GPA and overall
academic standing.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreSemesterResult(models.Model):
    _name = 'unicore.semester.result'
    _description = 'Semester Result'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'student_id, semester_id desc'
    _check_company_auto = True

    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    # --- ACADEMIC PERFORMANCE ---

    credits_attempted = fields.Float(
        string='Credits Attempted',
        default=0.0,
        digits=(5, 1),
        readonly=True,
    )
    credits_earned = fields.Float(
        string='Credits Earned',
        default=0.0,
        digits=(5, 1),
        readonly=True,
    )
    total_grade_points = fields.Float(
        string='Total Grade Points',
        default=0.0,
        digits=(7, 3),
        readonly=True,
    )
    semester_gpa = fields.Float(
        string='Semester GPA',
        default=0.0,
        digits=(4, 2),
        readonly=True,
        tracking=True,
    )
    courses_passed = fields.Integer(
        string='Courses Passed',
        default=0,
        readonly=True,
    )
    courses_failed = fields.Integer(
        string='Courses Failed',
        default=0,
        readonly=True,
    )

    # --- RESULT ---

    result_status = fields.Selection(
        string='Result',
        required=True,
        default='pending',
        tracking=True,
        selection=[
            ('pending', 'Pending'),
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('supplementary', 'Supplementary Required'),
            ('withheld', 'Result Withheld'),
        ],
    )
    remarks = fields.Text(string='Remarks')
    published_on = fields.Date(
        string='Published On',
        readonly=True,
    )
    is_published = fields.Boolean(
        string='Published',
        default=False,
        tracking=True,
    )

    _unique_student_semester_result = models.Constraint(
        'UNIQUE(student_id, semester_id)',
        'Semester result already exists for this student and semester.',
    )

    @api.model
    def generate_results_for_semester(self,
                                       semester_id,
                                       company_id):
        """
        Generate semester result records for all
        students who have at least one published
        or locked grade entry in this semester.
        Safe to re-run \u2014 existing results are
        updated, not duplicated.
        """
        GradeEntry = self.env['unicore.grade.entry']
        entries = GradeEntry.search([
            ('semester_id', '=', semester_id),
            ('company_id', '=', company_id),
            ('entry_state', 'in', ['published', 'locked']),
        ])
        student_ids = entries.mapped('student_id').ids
        processed = 0
        for student_id in list(set(student_ids)):
            student_entries = entries.filtered(
                lambda e: e.student_id.id == student_id
            )
            credits_attempted = sum(
                e.credit_hours for e in student_entries
            )
            credits_earned = sum(
                e.credit_hours for e in student_entries
                if e.is_pass
            )
            total_gp = sum(
                e.grade_points_earned
                for e in student_entries
            )
            sem_gpa = (
                round(total_gp / credits_attempted, 2)
                if credits_attempted > 0 else 0.0
            )
            courses_passed = len(student_entries.filtered(
                lambda e: e.is_pass
            ))
            courses_failed = len(student_entries.filtered(
                lambda e: not e.is_pass
            ))
            result_status = (
                'pass' if courses_failed == 0 else
                'supplementary' if courses_failed <= 2
                else 'fail'
            )
            existing = self.search([
                ('student_id', '=', student_id),
                ('semester_id', '=', semester_id),
            ], limit=1)
            vals = {
                'credits_attempted': credits_attempted,
                'credits_earned': credits_earned,
                'total_grade_points': total_gp,
                'semester_gpa': sem_gpa,
                'courses_passed': courses_passed,
                'courses_failed': courses_failed,
                'result_status': result_status,
            }
            if existing:
                existing.write(vals)
            else:
                vals.update({
                    'student_id': student_id,
                    'semester_id': semester_id,
                    'company_id': company_id,
                })
                self.create(vals)
            processed += 1
        return processed

    def action_publish_result(self):
        self.ensure_one()
        self.write({
            'is_published': True,
            'published_on': fields.Date.today(),
        })
        self.message_post(
            body=_('Semester result published. '
                   'GPA: %s, Result: %s')
                 % (self.semester_gpa,
                    self.result_status)
        )

    def action_withhold(self):
        self.ensure_one()
        self.result_status = 'withheld'
        self.message_post(
            body=_('Result withheld.')
        )
