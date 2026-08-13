"""Gap-1 fill: course.department_id is optional for non-legacy institutions.

- Legacy university (or unset profile) -> department_id required
  (same as Phase 0/1; the program anchor rule now mirrored on course).
- Any other institution type           -> course may be created without a
  department (K-12 schools / training centres have no faculty-dept chain).
"""

import odoo
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisCourseDepartmentTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Legacy baseline: no profile set.
        cls.company.institution_profile_id = False
        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'Test Faculty of Science',
            'code': 'TFSC',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'Test Physics',
            'code': 'TPHY',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })

    def _course_vals(self, **kw):
        vals = {
            'name': 'Test Course',
            'code': 'TCRS',
            'company_id': self.company.id,
        }
        vals.update(kw)
        return vals

    def test_01_legacy_course_requires_department(self):
        self.company.institution_profile_id = False
        with self.assertRaises(ValidationError):
            self.env['oacis.course'].create(
                self._course_vals(code='TCRS01'),
            )

    def test_02_legacy_course_with_department_ok(self):
        self.company.institution_profile_id = False
        course = self.env['oacis.course'].create(
            self._course_vals(
                code='TCRS02',
                department_id=self.department.id,
            ),
        )
        self.assertTrue(course.is_legacy_institution)
        self.assertEqual(course.department_id, self.department)
        self.assertEqual(course.academic_faculty_id, self.faculty)

    def test_03_school_course_without_department_ok(self):
        profile = self.env['oacis.institution.profile'].create({
            'name': 'Test School',
            'code': 'TEST-SCHOOL-DEPT',
            'institution_type': 'school',
            'is_legacy_university': False,
            'grading_scheme': 'simple_percentage',
        })
        self.company.institution_profile_id = profile.id
        course = self.env['oacis.course'].create(
            self._course_vals(code='TCRS03'),
        )
        self.assertFalse(course.is_legacy_institution)
        self.assertFalse(course.department_id)
        self.assertFalse(course.academic_faculty_id)

    def test_04_legacy_write_removing_department_fails(self):
        self.company.institution_profile_id = False
        course = self.env['oacis.course'].create(
            self._course_vals(
                code='TCRS04',
                department_id=self.department.id,
            ),
        )
        with self.assertRaises(ValidationError):
            course.write({'department_id': False})
        # Record stays consistent after failed write.
        self.assertEqual(course.department_id, self.department)
