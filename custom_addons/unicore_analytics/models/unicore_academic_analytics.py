"""
UniCore Academic Analytics
PostgreSQL VIEW-based models for grade distribution,
course performance and semester result analytics.
"""

from odoo import fields, models, tools
from odoo.orm.fields_misc import Id
import logging

_logger = logging.getLogger(__name__)


class UniCoreGradeDistributionReport(models.Model):
    _name = 'unicore.grade.distribution.report'
    _description = 'Grade Distribution Report'
    _auto = False
    _rec_name = 'course_id'
    _order = 'semester_id desc, course_id'

    id = Id()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        readonly=True,
    )
    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        readonly=True,
    )
    letter_grade = fields.Char(
        string='Letter Grade',
        readonly=True,
    )
    student_count = fields.Integer(
        string='Students',
        readonly=True,
    )
    pass_count = fields.Integer(
        string='Passed',
        readonly=True,
    )
    fail_count = fields.Integer(
        string='Failed',
        readonly=True,
    )
    avg_percentage = fields.Float(
        string='Avg Percentage',
        readonly=True,
        digits=(5, 1),
    )
    avg_grade_point = fields.Float(
        string='Avg Grade Point',
        readonly=True,
        digits=(4, 2),
    )
    pass_rate = fields.Float(
        string='Pass Rate %',
        readonly=True,
        digits=(5, 1),
    )

    def init(self):
        tools.drop_view_if_exists(
            self.env.cr,
            'unicore_grade_distribution_report'
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW
            unicore_grade_distribution_report AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    ge.company_id,
                    ge.course_id,
                    ge.semester_id,
                    COALESCE(ge.letter_grade, 'N/A')
                        AS letter_grade,
                    COUNT(ge.id) AS student_count,
                    COUNT(CASE WHEN ge.is_pass = TRUE
                        THEN 1 END) AS pass_count,
                    COUNT(CASE WHEN ge.is_pass = FALSE
                        THEN 1 END) AS fail_count,
                    ROUND(
                        AVG(ge.percentage)::numeric, 1
                    ) AS avg_percentage,
                    ROUND(
                        AVG(ge.grade_point)::numeric, 2
                    ) AS avg_grade_point,
                    ROUND(
                        (COUNT(CASE WHEN ge.is_pass = TRUE
                            THEN 1 END)::numeric
                        / NULLIF(COUNT(ge.id), 0)
                        * 100), 1
                    ) AS pass_rate
                FROM unicore_grade_entry ge
                WHERE ge.entry_state IN
                    ('published', 'locked')
                GROUP BY
                    ge.company_id,
                    ge.course_id,
                    ge.semester_id,
                    ge.letter_grade
            )
        """)


class UniCoreSemesterResultReport(models.Model):
    _name = 'unicore.semester.result.report'
    _description = 'Semester Result Analytics'
    _auto = False
    _rec_name = 'semester_id'
    _order = 'semester_id desc, program_id'

    id = Id()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        readonly=True,
    )
    program_id = fields.Many2one(
        comodel_name='unicore.program',
        string='Program',
        readonly=True,
    )
    result_status = fields.Selection(
        string='Result',
        readonly=True,
        selection=[
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('supplementary', 'Supplementary'),
            ('pending', 'Pending'),
        ],
    )
    student_count = fields.Integer(
        string='Students',
        readonly=True,
    )
    avg_semester_gpa = fields.Float(
        string='Avg Semester GPA',
        readonly=True,
        digits=(4, 2),
    )
    avg_credits_earned = fields.Float(
        string='Avg Credits Earned',
        readonly=True,
        digits=(5, 1),
    )

    def init(self):
        tools.drop_view_if_exists(
            self.env.cr,
            'unicore_semester_result_report'
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW
            unicore_semester_result_report AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    sr.company_id,
                    sr.semester_id,
                    s.program_id,
                    sr.result_status,
                    COUNT(sr.id) AS student_count,
                    ROUND(
                        AVG(sr.semester_gpa)::numeric, 2
                    ) AS avg_semester_gpa,
                    ROUND(
                        AVG(sr.credits_earned)::numeric, 1
                    ) AS avg_credits_earned
                FROM unicore_semester_result sr
                JOIN unicore_student s
                    ON s.id = sr.student_id
                WHERE sr.is_published = TRUE
                GROUP BY
                    sr.company_id,
                    sr.semester_id,
                    s.program_id,
                    sr.result_status
            )
        """)
