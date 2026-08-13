"""Phases 4-5 regression suite: cohort-driven enrollment defaults + intake automation.

Verifies that student enrollment carries the right cohort per program kind:

* Legacy (academic_year) -> `batch_year` only (unchanged).
* K-12 grade_batch      -> `grade_level_id` required (explicit, Phase 4).
* Training rolling      -> `cohort_start_date` required; auto-filled from
                          `admission_date` on create/enroll (Phase 5 intake
                          automation), explicit values never overwritten.

The existing student tests prove the legacy path is untouched; this suite pins
the new behavior. All new requirements are inert for legacy (academic_year)
programs, so existing university flows are byte-for-byte unchanged.
"""

import odoo
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'unit')
class UniCoreStudentCohortTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        # Deterministic legacy baseline: main company starts with NO profile.
        cls.company.institution_profile_id = False

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'P4 Faculty of Arts',
            'code': 'PFAC',  # faculty codes must be letters only
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'P4 English',
            'code': 'P4ENG',
            'faculty_id': cls.faculty.id,
        })
        cls.campus = cls.env['unicore.campus'].create({
            'name': 'P4 Main Campus',
            'code': 'P4CAMPUS',
            'company_id': cls.company.id,
        })
        cls.grade_type = cls.env.ref(
            'unicore_academic_generic.unit_type_grade_level')

    def _student_vals(self, **kw):
        vals = {
            'name': 'P4 Student',
            'gender': 'male',
            'date_of_birth': '2000-01-15',
            'email': 'p4.student@example.com',
            'mobile': '+919999999991',
            'company_id': self.company.id,
            'campus_id': self.campus.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        }
        vals.update(kw)
        return vals

    def _legacy_program(self, code='P4LEG'):
        return self.env['unicore.program'].create({
            'name': 'P4 Legacy B.A.',
            'code': code,
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of P4',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'department_id': self.department.id,
            'company_id': self.company.id,
        })

    def _school_kit(self, tag):
        """Switch the company to a K-12 school profile and return a grade unit."""
        self.company.institution_profile_id = self.env[
            'unicore.institution.profile'
        ].create({
            'name': 'P4 School %s' % tag,
            'code': 'P4SCH%s' % tag,
            'institution_type': 'school',
            'is_legacy_university': False,
        }).id
        return self.env['unicore.academic.unit'].create({
            'name': 'Grade 5',
            'code': 'P4G5',
            'unit_type_id': self.grade_type.id,
            'company_id': self.company.id,
        })

    def _school_program(self, code, cohort_kind, unit):
        return self.env['unicore.program'].create({
            'name': 'P4 School Program %s' % code,
            'code': code,
            'program_type': 'undergraduate',
            'degree_title': 'P4 Diploma',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'academic_unit_id': unit.id,
            'cohort_kind': cohort_kind,
        })

    def test_01_legacy_student_unchanged(self):
        """A legacy-university student needs no grade level / start date."""
        self.company.institution_profile_id = False
        program = self._legacy_program()
        student = self.env['unicore.student'].create(
            self._student_vals(program_id=program.id))
        self.assertEqual(student.cohort_kind, 'academic_year')
        self.assertFalse(student.grade_level_id)
        self.assertFalse(student.cohort_start_date)
        self.assertEqual(student.batch_year, 2025)
        self.assertEqual(student.cohort_label, 'Batch 2025')

    def test_02_grade_batch_requires_grade_level(self):
        """A grade-batch program student MUST have a grade level."""
        unit = self._school_kit('A')
        program = self._school_program('P4GB1', 'grade_batch', unit)
        with self.assertRaises(ValidationError):
            self.env['unicore.student'].create(
                self._student_vals(program_id=program.id,
                                   email='p4.gb.no@example.com'))
        student = self.env['unicore.student'].create(
            self._student_vals(program_id=program.id,
                               grade_level_id=unit.id,
                               email='p4.gb.yes@example.com'))
        self.assertEqual(student.cohort_kind, 'grade_batch')
        self.assertEqual(student.grade_level_id, unit)
        self.assertEqual(student.cohort_label, unit.display_name)

    def test_03_rolling_intake_auto_fills_start(self):
        """Phase 5: rolling intake auto-fills cohort_start_date from admission_date."""
        unit = self._school_kit('B')
        program = self._school_program('P4ROLL1', 'rolling', unit)
        student = self.env['unicore.student'].create(
            self._student_vals(program_id=program.id,
                               email='p4.roll.auto@example.com'))
        self.assertEqual(student.cohort_kind, 'rolling')
        self.assertEqual(str(student.cohort_start_date), '2025-06-01')
        self.assertEqual(student.cohort_label, '2025-06-01')

    def test_04_write_requires_grade_level(self):
        """Moving a student onto a grade-batch program enforces the grade."""
        legacy = self._legacy_program('P4LEGB')
        student = self.env['unicore.student'].create(
            self._student_vals(program_id=legacy.id,
                               email='p4.write@example.com'))
        unit = self._school_kit('C')
        gb = self._school_program('P4GB2', 'grade_batch', unit)
        with self.assertRaises(ValidationError):
            student.program_id = gb.id
        # The failed write left the legacy program in place.
        self.assertEqual(student.program_id, legacy)
        student.grade_level_id = unit.id
        student.program_id = gb.id
        self.assertEqual(student.cohort_kind, 'grade_batch')
        self.assertEqual(student.grade_level_id, unit)

    def test_05_label_follows_kind_on_switch(self):
        """cohort_label follows the program's cohort kind."""
        unit = self._school_kit('D')
        gb = self._school_program('P4GB3', 'grade_batch', unit)
        student = self.env['unicore.student'].create(
            self._student_vals(program_id=gb.id, grade_level_id=unit.id,
                               email='p4.switch@example.com'))
        self.assertEqual(student.cohort_label, unit.display_name)
        student.cohort_start_date = '2025-02-01'
        roll = self._school_program('P4ROLL2', 'rolling', unit)
        student.program_id = roll.id
        self.assertEqual(student.cohort_kind, 'rolling')
        self.assertEqual(student.cohort_label, '2025-02-01')

    def test_06_rolling_explicit_start_respected(self):
        """An explicitly provided cohort start date is never overwritten."""
        unit = self._school_kit('E')
        program = self._school_program('P4ROLL3', 'rolling', unit)
        student = self.env['unicore.student'].create(
            self._student_vals(program_id=program.id,
                               cohort_start_date='2025-01-15',
                               email='p4.roll.explicit@example.com'))
        self.assertEqual(str(student.cohort_start_date), '2025-01-15')
        self.assertEqual(student.cohort_label, '2025-01-15')

    def test_07_grade_batch_still_requires_grade(self):
        """Phase 5 keeps grade selection explicit: no auto-derivation."""
        unit = self._school_kit('F')
        program = self._school_program('P4GB4', 'grade_batch', unit)
        with self.assertRaises(ValidationError):
            self.env['unicore.student'].create(
                self._student_vals(program_id=program.id,
                                   email='p4.gb4.no@example.com'))

    def test_08_enroll_works_for_auto_filled_rolling(self):
        """Enrolling an auto-filled rolling student succeeds and carries the cohort."""
        unit = self._school_kit('G')
        program = self._school_program('P4ROLL4', 'rolling', unit)
        student = self.env['unicore.student'].create(
            self._student_vals(program_id=program.id,
                               email='p4.roll.enroll@example.com'))
        self.assertEqual(str(student.cohort_start_date), '2025-06-01')
        student.action_enroll()
        self.assertEqual(student.student_state, 'enrolled')
        self.assertEqual(student.cohort_label, '2025-06-01')
