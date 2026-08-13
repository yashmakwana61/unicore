"""Phase 6 regression suite: cohort roster & filtering.

Verifies the cohort-membership logic introduced in Phase 6:

* Legacy (academic_year) -> members = same program + same batch_year.
* K-12 grade_batch      -> members = same program + same grade_level_id.
* Training rolling      -> members = same program + same cohort_start_date.

A cohort roster lets staff see everyone in the same cohort (all Grade-5
students, all students in the Jan-2025 intake, all students in a batch). The
logic is purely additive and inert for legacy university flows (which already
group by batch year, so the legacy roster is just the existing batch view).
"""

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisStudentCohortRosterTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        # Deterministic legacy baseline: main company starts with NO profile.
        cls.company.institution_profile_id = False

        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'P6 Faculty of Arts',
            'code': 'PFAC',  # faculty codes must be letters only
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'P6 English',
            'code': 'P6ENG',
            'faculty_id': cls.faculty.id,
        })
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'P6 Main Campus',
            'code': 'P6CAMPUS',
            'company_id': cls.company.id,
        })
        cls.grade_type = cls.env.ref(
            'oacis_academic_generic.unit_type_grade_level')

    def _student_vals(self, **kw):
        vals = {
            'name': 'P6 Student',
            'gender': 'male',
            'date_of_birth': '2000-01-15',
            'email': 'p6.student@example.com',
            'mobile': '+919999999991',
            'company_id': self.company.id,
            'campus_id': self.campus.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        }
        vals.update(kw)
        return vals

    def _legacy_program(self, code='P6LEG'):
        return self.env['oacis.program'].create({
            'name': 'P6 Legacy B.A.',
            'code': code,
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of P6',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'department_id': self.department.id,
            'company_id': self.company.id,
        })

    def _school_kit(self, tag):
        self.company.institution_profile_id = self.env[
            'oacis.institution.profile'
        ].create({
            'name': 'P6 School %s' % tag,
            'code': 'P6SCH%s' % tag,
            'institution_type': 'school',
            'is_legacy_university': False,
        }).id
        return self.env['oacis.academic.unit'].create({
            'name': 'Grade 5',
            'code': 'P6G5',
            'unit_type_id': self.grade_type.id,
            'company_id': self.company.id,
        })

    def _school_program(self, code, cohort_kind, unit):
        return self.env['oacis.program'].create({
            'name': 'P6 School Program %s' % code,
            'code': code,
            'program_type': 'undergraduate',
            'degree_title': 'P6 Diploma',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'academic_unit_id': unit.id,
            'cohort_kind': cohort_kind,
        })

    def test_01_legacy_roster_by_batch(self):
        """Legacy members share program + batch_year."""
        self.company.institution_profile_id = False
        program = self._legacy_program()
        s1 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id,
                               email='p6.legacy.a@example.com'))
        s2 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id, batch_year=2025,
                               email='p6.legacy.b@example.com'))
        s3 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id, batch_year=2024,
                               email='p6.legacy.c@example.com'))
        self.assertEqual(s1.cohort_members_count, 2)
        self.assertEqual(s2.cohort_members_count, 2)
        self.assertEqual(s3.cohort_members_count, 1)
        domain = s1.action_open_cohort_members()['domain']
        self.assertEqual(
            set(self.env['oacis.student'].search(domain).ids),
            {s1.id, s2.id},
        )

    def test_02_grade_roster_by_grade_level(self):
        """K-12 members share program + grade level."""
        unit = self._school_kit('A')
        program = self._school_program('P6GB1', 'grade_batch', unit)
        other_unit = self.env['oacis.academic.unit'].create({
            'name': 'Grade 6',
            'code': 'P6G6',
            'unit_type_id': self.grade_type.id,
            'company_id': self.company.id,
        })
        s1 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id, grade_level_id=unit.id,
                               email='p6.gb.a@example.com'))
        s2 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id, grade_level_id=unit.id,
                               email='p6.gb.b@example.com'))
        s3 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id,
                               grade_level_id=other_unit.id,
                               email='p6.gb.c@example.com'))
        self.assertEqual(s1.cohort_members_count, 2)
        self.assertEqual(s2.cohort_members_count, 2)
        self.assertEqual(s3.cohort_members_count, 1)

    def test_03_rolling_roster_by_intake_date(self):
        """Rolling members share program + cohort start (auto-filled intake)."""
        unit = self._school_kit('B')
        program = self._school_program('P6ROLL1', 'rolling', unit)
        s1 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id, admission_date='2025-01-10',
                               email='p6.roll.a@example.com'))
        s2 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id, admission_date='2025-01-10',
                               email='p6.roll.b@example.com'))
        s3 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id, admission_date='2025-03-01',
                               email='p6.roll.c@example.com'))
        # Phase 5 auto-fill means cohort_start_date follows admission_date.
        self.assertEqual(str(s1.cohort_start_date), '2025-01-10')
        self.assertEqual(str(s3.cohort_start_date), '2025-03-01')
        self.assertEqual(s1.cohort_members_count, 2)
        self.assertEqual(s2.cohort_members_count, 2)
        self.assertEqual(s3.cohort_members_count, 1)

    def test_04_action_opens_roster(self):
        """action_open_cohort_members returns the same-cohort student list."""
        unit = self._school_kit('C')
        program = self._school_program('P6ROLL2', 'rolling', unit)
        s1 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id,
                               email='p6.action.a@example.com'))
        s2 = self.env['oacis.student'].create(
            self._student_vals(program_id=program.id,
                               email='p6.action.b@example.com'))
        action = s1.action_open_cohort_members()
        self.assertEqual(action['res_model'], 'oacis.student')
        self.assertEqual(action['view_mode'], 'list,form')
        self.assertEqual(
            set(self.env['oacis.student'].search(action['domain']).ids),
            {s1.id, s2.id},
        )
