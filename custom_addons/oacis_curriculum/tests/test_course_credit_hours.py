import odoo
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisCourseCreditHoursTest(TransactionCase):
    """Phase 2: course.credit_hours is conditionally required.

    - Legacy university (or unset profile) -> credit_hours > 0 required
      (same as Phase 0/1; the >0 cap plus the <=20 cap still apply).
    - Any other institution type            -> credit_hours may be 0.
    """

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

    def test_01_legacy_course_requires_credit_hours(self):
        self.company.institution_profile_id = False
        with self.assertRaises(ValidationError):
            self.env['oacis.course'].create({
                'name': 'Legacy Zero Credits',
                'code': 'TLCZERO',
                'credit_hours': 0.0,
                'department_id': self.department.id,
                'company_id': self.company.id,
            })

    def test_02_legacy_course_default_credit_hours(self):
        self.company.institution_profile_id = False
        course = self.env['oacis.course'].create({
            'name': 'Legacy Default',
            'code': 'TLCDEF',
            'department_id': self.department.id,
            'company_id': self.company.id,
        })
        self.assertEqual(course.credit_hours, 3.0)
        self.assertTrue(course.is_legacy_institution)

    def test_03_non_legacy_course_allows_zero_credit_hours(self):
        profile = self.env['oacis.institution.profile'].create({
            'name': 'Test School',
            'code': 'TEST-SCHOOL-CH',
            'institution_type': 'school',
            'is_legacy_university': False,
            'grading_scheme': 'simple_percentage',
        })
        self.company.institution_profile_id = profile.id
        course = self.env['oacis.course'].create({
            'name': 'School Zero Credits',
            'code': 'TSCZERO',
            'credit_hours': 0.0,
            'department_id': self.department.id,
            'company_id': self.company.id,
        })
        self.assertEqual(course.credit_hours, 0.0)
        self.assertFalse(course.is_legacy_institution)

    def test_04_credit_hours_cap_applies_to_all(self):
        self.company.institution_profile_id = False
        with self.assertRaises(ValidationError):
            self.env['oacis.course'].create({
                'name': 'Too Many Credits',
                'code': 'TLCHIGH',
                'credit_hours': 21.0,
                'department_id': self.department.id,
                'company_id': self.company.id,
            })
