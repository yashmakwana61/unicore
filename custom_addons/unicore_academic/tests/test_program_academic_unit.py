"""Phase 1 regression suite: academic hierarchy made optional.

Verifies the `is_legacy_university` compatibility shim on `unicore.program`:

* Legacy university (or unset institution profile) keeps the Department
  mandatory and derives company_id / faculty_id from it (100% unchanged).
* A non-legacy institution (e.g. K-12 school / training) may anchor a program
  directly on a generic `unicore.academic.unit` with no Department at all.

The existing university tests in the other 14 modules are the real proof that
the legacy path is untouched; this suite pins the new behavior.
"""

import odoo
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'unit')
class UniCoreProgramAcademicUnitTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        # Ensure a deterministic legacy baseline for every test in this class:
        # the main company starts with NO institution profile (= legacy).
        cls.company.institution_profile_id = False

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'P1 Faculty of Arts',
            'code': 'ARTS',  # faculty codes must be letters only
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'P1 English',
            'code': 'P1ENG',
            'faculty_id': cls.faculty.id,
        })
        cls.grade_type = cls.env.ref(
            'unicore_academic_generic.unit_type_grade_level')

    def _base_vals(self, **kw):
        vals = {
            'name': 'P1 Program',
            'code': 'P1PRG',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of P1',
            'duration_years': 3.0,
            'credit_system': 'credit_hours',
            'total_credits': 90,
        }
        vals.update(kw)
        return vals

    def _school_profile(self, code='P1K12'):
        return self.env['unicore.institution.profile'].create({
            'name': 'P1 K-12 School',
            'code': code,
            'institution_type': 'school',
            'is_legacy_university': False,
        })

    def test_01_legacy_program_requires_department(self):
        """A program without a Department is rejected for a legacy university."""
        self.assertFalse(self.company.institution_profile_id)
        with self.assertRaises(ValidationError):
            self.env['unicore.program'].create(self._base_vals(code='P1NODEP'))

    def test_02_legacy_program_with_department_ok(self):
        """Legacy programs keep deriving faculty/company from the Department."""
        program = self.env['unicore.program'].create(self._base_vals(
            code='P1DEP', department_id=self.department.id))
        self.assertTrue(program)
        self.assertEqual(program.department_id, self.department)
        self.assertEqual(program.faculty_id, self.faculty)
        self.assertEqual(program.company_id, self.company)
        self.assertTrue(program.is_legacy_institution)

    def test_03_non_legacy_program_via_academic_unit(self):
        """A K-12-style company anchors programs on academic units, no Dept."""
        self.company.institution_profile_id = self._school_profile().id
        self.assertFalse(self.company.institution_profile_id.is_legacy_university)

        grade = self.env['unicore.academic.unit'].create({
            'name': 'Grade 5',
            'code': 'P1G5',
            'unit_type_id': self.grade_type.id,
            'company_id': self.company.id,
        })
        program = self.env['unicore.program'].create(self._base_vals(
            code='P1K12A', academic_unit_id=grade.id))

        self.assertTrue(program)
        self.assertEqual(program.academic_unit_id, grade)
        self.assertFalse(program.department_id)
        self.assertFalse(program.faculty_id)
        self.assertEqual(program.company_id, self.company)
        self.assertFalse(program.is_legacy_institution)

    def test_04_non_legacy_program_requires_an_anchor(self):
        """Even non-legacy programs need at least one anchor."""
        self.company.institution_profile_id = self._school_profile('P1TR').id
        with self.assertRaises(ValidationError):
            self.env['unicore.program'].create(self._base_vals(code='P1NOANCHOR'))

    def test_05_legacy_flag_follows_company_profile(self):
        """is_legacy_institution reflects the company profile, not the record."""
        program = self.env['unicore.program'].create(self._base_vals(
            code='P1FLAG', department_id=self.department.id))
        self.assertTrue(program.is_legacy_institution)

        self.company.institution_profile_id = self._school_profile('P1SB').id
        # Non-stored computed field: re-reading after the profile change must
        # reflect the new institution mode.
        self.assertFalse(program.is_legacy_institution)

    def test_06_legacy_anchor_cannot_be_dropped(self):
        """Removing the Department from a legacy program is rejected."""
        program = self.env['unicore.program'].create(self._base_vals(
            code='P1DROP', department_id=self.department.id))
        with self.assertRaises(ValidationError):
            program.department_id = False
