"""Smoke / regression suite for oacis_institution_profile (Phase 0).

Verifies the seeded University-Legacy profile (the compatibility shim),
terminology defaults, the nullable res.company wiring, and the profile/feature
catalogs. This is the regression baseline for Phase 1 (is_legacy_university
compatibility) and Phase 5 (onboarding templates).
"""

from psycopg2 import IntegrityError

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisInstitutionProfileTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.profile_legacy = cls.env.ref(
            'oacis_institution_profile.profile_university_legacy')
        cls.terminology_legacy = cls.env.ref(
            'oacis_institution_profile.terminology_university_legacy')
        cls.feature_ids = cls.env['oacis.institution.feature'].search(
            [], order='sequence')

    def test_01_seed_institution_profile(self):
        """University (Legacy) profile ships with full legacy behavior."""
        self.assertEqual(self.profile_legacy.code, 'UNI_LEGACY')
        self.assertEqual(self.profile_legacy.institution_type, 'university')
        self.assertTrue(self.profile_legacy.is_legacy_university)
        self.assertEqual(self.profile_legacy.calendar_mode, 'semester')
        self.assertEqual(self.profile_legacy.grading_scheme, 'credit_gpa')
        self.assertEqual(self.profile_legacy.terminology_profile_id,
                         self.terminology_legacy)

    def test_02_seed_terminology(self):
        """Legacy terminology keeps the university vocabulary intact."""
        self.assertEqual(self.terminology_legacy.code, 'UNI_LEGACY')
        self.assertEqual(self.terminology_legacy.term_faculty, 'Faculty')
        self.assertEqual(self.terminology_legacy.term_department, 'Department')
        self.assertEqual(self.terminology_legacy.term_program, 'Program')
        self.assertEqual(self.terminology_legacy.term_student, 'Student')
        self.assertEqual(self.terminology_legacy.term_semester, 'Semester')

    def test_03_seed_features_catalog(self):
        """Thirteen optional features are seeded."""
        self.assertEqual(len(self.feature_ids), 13)
        codes = set(self.feature_ids.mapped('code'))
        for expected in ('HOSTEL', 'TRANSPORT', 'LIBRARY', 'ALUMNI',
                         'CONVOCATION', 'SCHOLARSHIP', 'THESIS', 'CRM',
                         'ADMISSION', 'WEBSITE', 'ATTENDANCE', 'EXAM', 'FEES'):
            self.assertIn(expected, codes)

    def test_04_legacy_profile_uses_all_unit_levels(self):
        """The legacy profile references all eight seeded academic unit levels."""
        unit_types = self.profile_legacy.academic_unit_level_ids
        self.assertEqual(len(unit_types), 8)
        codes = set(unit_types.mapped('code'))
        self.assertIn('FAC', codes)
        self.assertIn('DEP', codes)
        self.assertIn('GRADE', codes)

    def test_05_company_profile_nullable_and_related(self):
        """Backfill attaches UNI_LEGACY by default; terminology follows; nullable.

        Since 19.0.1.1.0 the post-install backfill attaches the University
        (Legacy) profile to every company, activating the profile driver with
        zero behavior change. The field remains nullable so a company can be
        detached. Uses the existing main company (a fresh res.company cannot be
        created in Odoo 19 CE tests due to an unrelated NOT NULL quirk on the
        internally created res.partner). All changes roll back with the test.
        """
        company = self.env.company
        self.assertEqual(company.institution_profile_id, self.profile_legacy)
        self.assertEqual(company.terminology_profile_id, self.terminology_legacy)

        company.institution_profile_id = False
        self.assertFalse(company.terminology_profile_id)

        company.institution_profile_id = self.profile_legacy.id
        self.assertEqual(company.terminology_profile_id, self.terminology_legacy)

    def test_06_unique_profile_code(self):
        """Profile codes must be unique."""
        with self.assertRaises(IntegrityError):
            self.env['oacis.institution.profile'].create({
                'name': 'Duplicate', 'code': 'UNI_LEGACY',
            })

    def test_07_action_open_institution_profiles(self):
        """Convenience action opens the profile list."""
        action = self.profile_legacy.action_open_institution_profiles()
        self.assertEqual(action['res_model'], 'oacis.institution.profile')

    def test_08_create_school_like_profile(self):
        """A school-style profile can be modeled without legacy flag."""
        school = self.env['oacis.institution.profile'].create({
            'name': 'K-12 School (Pilot)',
            'code': 'K12_PILOT',
            'institution_type': 'school',
            'is_legacy_university': False,
            'calendar_mode': 'annual',
            'grading_scheme': 'simple_percentage',
        })
        self.assertEqual(school.institution_type, 'school')
        self.assertFalse(school.is_legacy_university)
        self.assertEqual(school.calendar_mode, 'annual')
        self.assertEqual(school.grading_scheme, 'simple_percentage')
