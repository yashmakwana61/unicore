"""
UniCore Student Analytics
PostgreSQL VIEW-based read-only models for
student enrollment and demographic analytics.
"""

from odoo import fields, models, tools
from odoo.orm.fields_misc import Id
import logging

_logger = logging.getLogger(__name__)


class UniCoreStudentEnrollmentReport(models.Model):
    _name = 'unicore.student.enrollment.report'
    _description = 'Student Enrollment Report'
    _auto = False
    _rec_name = 'program_id'
    _order = 'batch_year desc, program_id'

    id = Id()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        readonly=True,
    )
    program_id = fields.Many2one(
        comodel_name='unicore.program',
        string='Program',
        readonly=True,
    )
    batch_year = fields.Integer(
        string='Batch Year',
        readonly=True,
    )
    # --- COHORT (Gap-4 fill) ---
    cohort_kind = fields.Selection(
        string='Cohort Kind',
        readonly=True,
        selection=[
            ('academic_year', 'Academic Year / Batch'),
            ('grade_batch', 'Grade-Level Batch'),
            ('rolling', 'Rolling Intake'),
        ],
        help='How students of the program are grouped into cohorts.',
    )
    grade_level_id = fields.Many2one(
        comodel_name='unicore.academic.unit',
        string='Grade Level',
        readonly=True,
    )
    cohort_start_date = fields.Date(
        string='Cohort Start Date',
        readonly=True,
    )
    gender = fields.Selection(
        string='Gender',
        readonly=True,
        selection=[
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
        ],
    )
    student_state = fields.Selection(
        string='Student State',
        readonly=True,
        selection=[
            ('enrolled', 'Enrolled'),
            ('active', 'Active'),
            ('graduated', 'Graduated'),
            ('dropped', 'Dropped'),
            ('suspended', 'Suspended'),
        ],
    )
    student_count = fields.Integer(
        string='Student Count',
        readonly=True,
    )
    avg_cgpa = fields.Float(
        string='Average CGPA',
        readonly=True,
        digits=(4, 2),
    )
    max_cgpa = fields.Float(
        string='Max CGPA',
        readonly=True,
        digits=(4, 2),
    )
    min_cgpa = fields.Float(
        string='Min CGPA',
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
            'unicore_student_enrollment_report'
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW
            unicore_student_enrollment_report AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    s.company_id,
                    s.program_id,
                    s.batch_year,
                    s.cohort_kind,
                    s.grade_level_id,
                    s.cohort_start_date,
                    s.gender,
                    s.student_state,
                    COUNT(s.id) AS student_count,
                    ROUND(
                        AVG(s.cgpa)::numeric, 2
                    ) AS avg_cgpa,
                    ROUND(
                        MAX(s.cgpa)::numeric, 2
                    ) AS max_cgpa,
                    ROUND(
                        MIN(s.cgpa)::numeric, 2
                    ) AS min_cgpa,
                    ROUND(
                        AVG(s.total_credits_earned)
                        ::numeric, 1
                    ) AS avg_credits_earned
                FROM unicore_student s
                WHERE s.active = TRUE
                GROUP BY
                    s.company_id,
                    s.program_id,
                    s.batch_year,
                    s.cohort_kind,
                    s.grade_level_id,
                    s.cohort_start_date,
                    s.gender,
                    s.student_state
            )
        """)


class UniCoreAttendanceReport(models.Model):
    _name = 'unicore.attendance.report'
    _description = 'Attendance Analytics Report'
    _auto = False
    _rec_name = 'course_offering_id'
    _order = 'semester_id desc, course_offering_id'

    id = Id()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        readonly=True,
    )
    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
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
    student_count = fields.Integer(
        string='Students',
        readonly=True,
    )
    shortage_count = fields.Integer(
        string='Students with Shortage',
        readonly=True,
    )
    avg_attendance_pct = fields.Float(
        string='Avg Attendance %',
        readonly=True,
        digits=(5, 1),
    )
    min_attendance_pct = fields.Float(
        string='Min Attendance %',
        readonly=True,
        digits=(5, 1),
    )
    shortage_rate = fields.Float(
        string='Shortage Rate %',
        readonly=True,
        digits=(5, 1),
    )

    def init(self):
        tools.drop_view_if_exists(
            self.env.cr,
            'unicore_attendance_report'
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW
            unicore_attendance_report AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    ar.company_id,
                    tte.course_offering_id,
                    co.course_id,
                    co.semester_id,
                    COUNT(DISTINCT ar.student_id)
                        AS student_count,
                    COUNT(DISTINCT CASE
                        WHEN ar.shortage_alert = TRUE
                        THEN ar.student_id END)
                        AS shortage_count,
                    ROUND(
                        AVG(ar.cumulative_attendance_percentage)
                        ::numeric, 1
                    ) AS avg_attendance_pct,
                    ROUND(
                        MIN(ar.cumulative_attendance_percentage)
                        ::numeric, 1
                    ) AS min_attendance_pct,
                    ROUND(
                        (COUNT(DISTINCT CASE
                            WHEN ar.shortage_alert = TRUE
                            THEN ar.student_id END)::numeric
                        / NULLIF(COUNT(DISTINCT ar.student_id), 0)
                        * 100), 1
                    ) AS shortage_rate
                FROM unicore_attendance_record ar
                JOIN unicore_attendance_session ats
                    ON ats.id = ar.session_id
                JOIN unicore_timetable_entry tte
                    ON tte.id = ats.timetable_entry_id
                JOIN unicore_course_offering co
                    ON co.id = tte.course_offering_id
                WHERE ar.active = TRUE
                GROUP BY
                    ar.company_id,
                    tte.course_offering_id,
                    co.course_id,
                    co.semester_id
            )
        """)
