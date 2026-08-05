"""Gap-3: admission cohort binding.

Verifies that admission applicants can carry a K-12 grade level, that
grade-batch (K-12) programs require one, and that admission confirmation
propagates it to the created student.
"""

from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('unicore', 'unit')
class UniCoreAdmissionCohortTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # K-12 school profile (dept not required for programs).
        cls.company.institution_profile_id = cls.env[
            'unicore.institution.profile'
        ].create({
            'name': 'A School',
            'code': 'ASCH',
            'institution_type': 'school',
            'is_legacy_university': False,
        }).id

        cls.grade_type = cls.env.ref(
            'unicore_academic_generic.unit_type_grade_level')
        cls.grade = cls.env['unicore.academic.unit'].create({
            'name': 'Grade 5',
            'code': 'AG5',
            'unit_type_id': cls.grade_type.id,
            'company_id': cls.company.id,
        })

        cls.campus = cls.env['unicore.campus'].create({
            'name': 'A Campus',
            'code': 'ACMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['unicore.academic.year'].create({
            'name': '2025-2026',
            'code': '2025',
            'date_start': '2025-06-01',
            'date_end': '2026-05-31',
        })
        cls.cycle = cls.env['unicore.admission.cycle'].create({
            'name': 'A Intake 2025-26',
            'code': 'AIN-2526',
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2025-03-01',
            'end_date': '2025-08-31',
            'state': 'active',
            'company_id': cls.company.id,
        })

    def _program(self, code, cohort_kind):
        return self.env['unicore.program'].create({
            'name': 'A Program %s' % code,
            'code': code,
            'program_type': 'undergraduate',
            'degree_title': 'A Diploma',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'academic_unit_id': self.grade.id,
            'cohort_kind': cohort_kind,
        })

    def _applicant_vals(self, program_id, grade_id=False):
        vals = {
            'name': 'Asha Patel',
            'email': 'asha.patel@example.com',
            'mobile': '9111111111',
            'gender': 'female',
            'date_of_birth': date(2010, 5, 15),
            'cycle_id': self.cycle.id,
            'campus_id': self.campus.id,
            'program_id': program_id,
            'company_id': self.company.id,
        }
        if grade_id:
            vals['grade_level_id'] = grade_id
        return vals

    def _confirm(self, applicant):
        applicant.write({'state': 'fee_pending'})
        applicant.action_confirm_admission()
        return applicant.student_id

    def test_01_grade_batch_requires_grade_level(self):
        """A grade-batch (K-12) applicant must carry a grade level."""
        program = self._program('AGB', 'grade_batch')
        with self.assertRaises(ValidationError):
            self.env['unicore.admission.applicant'].create(
                self._applicant_vals(program.id))

    def test_02_grade_batch_confirm_binds_grade(self):
        """Confirming a grade-batch applicant propagates the grade level."""
        program = self._program('AGB2', 'grade_batch')
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals(program.id, grade_id=self.grade.id))
        self.assertEqual(applicant.cohort_kind, 'grade_batch')
        self.assertEqual(applicant.grade_level_id, self.grade)

        student = self._confirm(applicant)
        self.assertEqual(student.grade_level_id, self.grade)
        self.assertEqual(student.cohort_kind, 'grade_batch')
        self.assertEqual(student.program_id, program)
        self.assertEqual(student.admission_number, applicant.application_number)

    def test_03_rolling_confirm_auto_start(self):
        """Rolling-intake applicants confirm without grade and get a start date."""
        program = self._program('ARL', 'rolling')
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals(program.id))
        self.assertEqual(applicant.cohort_kind, 'rolling')
        self.assertFalse(applicant.grade_level_id)

        student = self._confirm(applicant)
        self.assertFalse(student.grade_level_id)
        self.assertEqual(student.cohort_kind, 'rolling')
        self.assertEqual(student.cohort_start_date, student.admission_date)

    def test_04_academic_year_confirm_unchanged(self):
        """Academic-year (legacy-style) applicants confirm unchanged."""
        program = self._program('AAY', 'academic_year')
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals(program.id))
        self.assertEqual(applicant.cohort_kind, 'academic_year')

        student = self._confirm(applicant)
        self.assertFalse(student.grade_level_id)
        self.assertEqual(student.cohort_kind, 'academic_year')
        # batch year derived from the cycle academic year code suffix
        self.assertEqual(student.batch_year, 2025)
