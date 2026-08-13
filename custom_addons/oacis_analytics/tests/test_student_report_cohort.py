"""Gap-4: student enrollment report cohort dimensions.

Verifies the SQL-view analytics model surfaces cohort_kind / grade_level_id /
cohort_start_date and can be grouped by grade level.
"""

from datetime import date

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('oacis', 'unit')
class OacisStudentReportCohortTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # K-12 school profile (no department required on programs).
        cls.company.institution_profile_id = cls.env[
            'oacis.institution.profile'
        ].create({
            'name': 'R School',
            'code': 'RSCH',
            'institution_type': 'school',
            'is_legacy_university': False,
        }).id

        cls.grade_type = cls.env.ref(
            'oacis_academic_generic.unit_type_grade_level')
        cls.grade = cls.env['oacis.academic.unit'].create({
            'name': 'Grade 5',
            'code': 'RG5',
            'unit_type_id': cls.grade_type.id,
            'company_id': cls.company.id,
        })

        cls.campus = cls.env['oacis.campus'].create({
            'name': 'R Campus',
            'code': 'RCMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': '2025-2026',
            'code': '2025',
            'date_start': '2025-06-01',
            'date_end': '2026-05-31',
        })

    def _program(self, code, cohort_kind):
        return self.env['oacis.program'].create({
            'name': 'R Program %s' % code,
            'code': code,
            'program_type': 'undergraduate',
            'degree_title': 'R Diploma',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'academic_unit_id': self.grade.id,
            'cohort_kind': cohort_kind,
        })

    def _student(self, name, program, grade=False):
        vals = {
            'name': name,
            'email': '%s@example.com' % name.lower(),
            'mobile': '9000000000',
            'gender': 'female',
            'date_of_birth': date(2010, 5, 15),
            'campus_id': self.campus.id,
            'program_id': program.id,
            'admission_date': fields.Date.today(),
            'batch_year': 2025,
            'company_id': self.company.id,
        }
        if grade:
            vals['grade_level_id'] = grade.id
        return self.env['oacis.student'].create(vals)

    def test_01_view_returns_cohort_rows(self):
        """The report surfaces cohort_kind and grade_level for students."""
        program = self._program('RGB', 'grade_batch')
        self._student('G1', program, grade=self.grade)
        self._student('G2', program, grade=self.grade)
        # The report is a SQL view: flush ORM changes first so the stored
        # related ``student.cohort_kind`` is visible to the view query.
        self.env.flush_all()
        rows = self.env['oacis.student.enrollment.report'].search(
            [('program_id', '=', program.id)])
        self.assertTrue(rows)
        row = rows[0]
        self.assertEqual(row.cohort_kind, 'grade_batch')
        self.assertEqual(row.grade_level_id, self.grade)
        self.assertEqual(row.student_count, 2)

    def test_02_group_by_grade_level(self):
        """read_group can break the report down by grade level."""
        program = self._program('RGB2', 'grade_batch')
        grade2 = self.env['oacis.academic.unit'].create({
            'name': 'Grade 6',
            'code': 'RG6',
            'unit_type_id': self.grade_type.id,
            'company_id': self.company.id,
        })
        self._student('A1', program, grade=self.grade)
        self._student('A2', program, grade=self.grade)
        self._student('A3', program, grade=grade2)

        grouped = self.env[
            'oacis.student.enrollment.report'
        ].read_group(
            [('program_id', '=', program.id)],
            ['student_count'],
            ['grade_level_id'])
        by_grade = {
            g['grade_level_id'][0]: g['student_count'] for g in grouped
        }
        self.assertEqual(by_grade.get(self.grade.id), 2)
        self.assertEqual(by_grade.get(grade2.id), 1)
