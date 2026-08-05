"""Phase 3 regression suite: cohort kinds on unicore.program.

Verifies the `cohort_kind` shim:

* Legacy universities (or unset institution profile) are locked to
  'academic_year' cohorts (100% unchanged behavior).
* Non-legacy institutions (K-12 school / training / coaching) may use
  'grade_batch' or 'rolling' cohorts.

The existing university tests in the other modules prove the legacy path is
untouched; this suite pins the new behavior.
"""

import odoo
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'unit')
class UniCoreProgramCohortKindTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        # Deterministic legacy baseline: main company starts with NO profile.
        cls.company.institution_profile_id = False

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'P3 Faculty of Arts',
            'code': 'PFAC',  # faculty codes must be letters only
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'P3 English',
            'code': 'P3ENG',
            'faculty_id': cls.faculty.id,
        })
        cls.grade_type = cls.env.ref(
            'unicore_academic_generic.unit_type_grade_level')

    def _base_vals(self, **kw):
        vals = {
            'name': 'P3 Program',
            'code': 'P3PRG',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of P3',
            'duration_years': 3.0,
            'credit_system': 'credit_hours',
            'total_credits': 90,
        }
        vals.update(kw)
        return vals

    def _school_profile(self, code='P3K12'):
        return self.env['unicore.institution.profile'].create({
            'name': 'P3 K-12 School',
            'code': code,
            'institution_type': 'school',
            'is_legacy_university': False,
        })

    def test_01_legacy_default_cohort_kind(self):
        """Legacy programs default to academic_year cohorts."""
        program = self.env['unicore.program'].create(self._base_vals(
            code='P3DEF', department_id=self.department.id))
        self.assertTrue(program.is_legacy_institution)
        self.assertEqual(program.cohort_kind, 'academic_year')
        self.assertTrue(program.cohort_grouping_label)

    def test_02_legacy_cannot_use_grade_batch(self):
        """A legacy university cannot create a grade_batch program."""
        with self.assertRaises(ValidationError):
            self.env['unicore.program'].create(self._base_vals(
                code='P3GB', department_id=self.department.id,
                cohort_kind='grade_batch'))

    def test_03_legacy_cannot_use_rolling(self):
        """A legacy university cannot create a rolling-intake program."""
        with self.assertRaises(ValidationError):
            self.env['unicore.program'].create(self._base_vals(
                code='P3ROLL', department_id=self.department.id,
                cohort_kind='rolling'))

    def test_04_school_grade_batch_ok(self):
        """A K-12 school anchors a grade_batch program on a grade-level unit."""
        self.company.institution_profile_id = self._school_profile().id
        grade = self.env['unicore.academic.unit'].create({
            'name': 'Grade 5',
            'code': 'P3G5',
            'unit_type_id': self.grade_type.id,
            'company_id': self.company.id,
        })
        program = self.env['unicore.program'].create(self._base_vals(
            code='P3K12A', academic_unit_id=grade.id,
            cohort_kind='grade_batch'))
        self.assertTrue(program)
        self.assertFalse(program.is_legacy_institution)
        self.assertEqual(program.cohort_kind, 'grade_batch')
        self.assertEqual(
            program.cohort_grouping_label,
            'Grouped by grade level within the academic year',
        )

    def test_05_school_rolling_ok(self):
        """A training centre anchors a rolling-intake program on a unit."""
        self.company.institution_profile_id = self._school_profile('P3TR').id
        wing = self.env['unicore.academic.unit'].create({
            'name': 'Test Wing',
            'code': 'P3WNG',
            'unit_type_id': self.grade_type.id,
            'company_id': self.company.id,
        })
        program = self.env['unicore.program'].create(self._base_vals(
            code='P3ROLLA', academic_unit_id=wing.id,
            cohort_kind='rolling'))
        self.assertFalse(program.is_legacy_institution)
        self.assertEqual(program.cohort_kind, 'rolling')
        self.assertEqual(
            program.cohort_grouping_label,
            'Rolling intake cohorts by start date',
        )

    def test_06_legacy_write_locked(self):
        """Changing cohort_kind away from academic_year on a legacy program is
        rejected at write time too."""
        program = self.env['unicore.program'].create(self._base_vals(
            code='P3WRLOCK', department_id=self.department.id))
        self.assertEqual(program.cohort_kind, 'academic_year')
        with self.assertRaises(ValidationError):
            program.cohort_kind = 'grade_batch'

    def test_07_label_follows_kind(self):
        """cohort_grouping_label reflects the current cohort_kind."""
        self.company.institution_profile_id = self._school_profile('P3LB').id
        unit = self.env['unicore.academic.unit'].create({
            'name': 'Grade 7',
            'code': 'P3G7',
            'unit_type_id': self.grade_type.id,
            'company_id': self.company.id,
        })
        program = self.env['unicore.program'].create(self._base_vals(
            code='P3LBL', academic_unit_id=unit.id,
            cohort_kind='grade_batch'))
        self.assertEqual(
            program.cohort_grouping_label,
            'Grouped by grade level within the academic year',
        )
        program.cohort_kind = 'rolling'
        self.assertEqual(
            program.cohort_grouping_label,
            'Rolling intake cohorts by start date',
        )
