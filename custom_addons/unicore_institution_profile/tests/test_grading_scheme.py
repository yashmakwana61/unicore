from psycopg2 import IntegrityError

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'unit')
class UniCoreGradingSchemeTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Legacy baseline: no profile set -> effective scheme = credit_gpa.
        cls.company.institution_profile_id = False

    def test_01_scheme_create(self):
        scheme = self.env['unicore.grading.scheme'].create({
            'name': 'Test Credit GPA',
            'code': 'TEST_CGPA',
            'scheme_type': 'credit_gpa',
            'sequence': 10,
        })
        self.assertEqual(scheme.scheme_type, 'credit_gpa')
        self.assertEqual(scheme.name, 'Test Credit GPA')

    def test_02_scheme_code_unique(self):
        self.env['unicore.grading.scheme'].create({
            'name': 'Test Weighted',
            'code': 'TEST_WPCT',
            'scheme_type': 'weighted_percentage',
        })
        with self.assertRaises(IntegrityError):
            self.env['unicore.grading.scheme'].create({
                'name': 'Test Duplicate',
                'code': 'TEST_WPCT',
                'scheme_type': 'simple_percentage',
            })

    def test_03_seeded_schemes_exist(self):
        scheme = self.env.ref(
            'unicore_institution_profile.grading_scheme_credit_gpa',
        )
        self.assertEqual(scheme.scheme_type, 'credit_gpa')
        self.assertTrue(scheme.is_default)

    def test_04_profile_effective_scheme_legacy_fallback(self):
        profile = self.env['unicore.institution.profile'].create({
            'name': 'Test Legacy Profile',
            'code': 'TEST-LEGACY',
            'is_legacy_university': True,
            'grading_scheme': 'credit_gpa',
        })
        self.assertEqual(profile.effective_grading_scheme, 'credit_gpa')

    def test_05_profile_effective_scheme_scheme_record(self):
        scheme = self.env.ref(
            'unicore_institution_profile.grading_scheme_simple_percentage',
        )
        profile = self.env['unicore.institution.profile'].create({
            'name': 'Test School Profile',
            'code': 'TEST-SCHOOL',
            'institution_type': 'school',
            'is_legacy_university': False,
            'grading_scheme': 'credit_gpa',
            'grading_scheme_id': scheme.id,
        })
        self.assertEqual(
            profile.effective_grading_scheme, 'simple_percentage',
        )

    def test_06_company_helper_no_profile(self):
        self.company.institution_profile_id = False
        self.assertEqual(
            self.company._get_effective_grading_scheme(), 'credit_gpa',
        )

    def test_07_company_helper_profile_legacy(self):
        profile = self.env['unicore.institution.profile'].create({
            'name': 'Test Legacy Profile 2',
            'code': 'TEST-LEGACY2',
            'is_legacy_university': True,
            'grading_scheme': 'credit_gpa',
        })
        self.company.institution_profile_id = profile.id
        self.assertEqual(
            self.company._get_effective_grading_scheme(), 'credit_gpa',
        )

    def test_08_company_helper_profile_scheme_record(self):
        scheme = self.env.ref(
            'unicore_institution_profile.grading_scheme_pass_fail',
        )
        profile = self.env['unicore.institution.profile'].create({
            'name': 'Test PF Profile',
            'code': 'TEST-PF',
            'institution_type': 'school',
            'is_legacy_university': False,
            'grading_scheme': 'credit_gpa',
            'grading_scheme_id': scheme.id,
        })
        self.company.institution_profile_id = profile.id
        self.assertEqual(
            self.company._get_effective_grading_scheme(), 'pass_fail',
        )
