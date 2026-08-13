"""Phase 8 regression suite: terminology label resolution + K-12 seeds.

Verifies that terminology profiles are actually consumable (they previously
existed but were never applied):

* ``resolve_label()`` returns the substituted label or a fallback.
* ``res.company.get_term_label()`` resolves through the company's profile
  (no profile / legacy => generic labels, unchanged).
* The seeded K-12 School profile + terminology are wired and coherent.
"""

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisTerminologyTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.terminology_legacy = cls.env.ref(
            'oacis_institution_profile.terminology_university_legacy')
        cls.terminology_school = cls.env.ref(
            'oacis_institution_profile.terminology_school_k12')
        cls.profile_school = cls.env.ref(
            'oacis_institution_profile.profile_school_k12')

    def test_01_resolve_label_legacy(self):
        """Legacy terminology resolves to the university vocabulary."""
        term = self.terminology_legacy
        self.assertEqual(term.resolve_label('semester'), 'Semester')
        self.assertEqual(term.resolve_label('program'), 'Program')
        self.assertEqual(term.resolve_label('academic_year'), 'Academic Year')
        # An explicit default is ignored when the profile defines the label.
        self.assertEqual(term.resolve_label('semester', default='Term'),
                         'Semester')
        # Unknown concept resolves to the default, else the concept key.
        self.assertEqual(term.resolve_label('unknown'), 'unknown')
        self.assertEqual(term.resolve_label('unknown', default='X'), 'X')

    def test_02_resolve_label_blank_falls_back(self):
        """Blank terms fall back to the default / generic label."""
        term = self.env['oacis.terminology.profile'].create({
            'name': 'Blank Terms',
            'code': 'BLANK',
            'term_faculty': '',
        })
        self.assertEqual(term.resolve_label('faculty', default='Wing'), 'Wing')
        self.assertEqual(term.resolve_label('faculty'), 'Faculty')  # generic
        self.assertEqual(term.resolve_label('semester', default='Term'), 'Term')

    def test_03_company_get_term_label(self):
        """Company resolution: no profile -> default; legacy -> unchanged;
        school -> K-12 vocabulary."""
        company = self.env.company
        company.institution_profile_id = False
        self.assertEqual(
            company.get_term_label('semester', default='Semester'), 'Semester')
        self.assertIsNone(company.get_term_label('semester'))

        company.institution_profile_id = self.env.ref(
            'oacis_institution_profile.profile_university_legacy').id
        self.assertEqual(
            company.get_term_label('semester', default='Semester'), 'Semester')
        self.assertEqual(company.get_term_label('program'), 'Program')

        company.institution_profile_id = self.profile_school.id
        self.assertEqual(
            company.get_term_label('semester', default='Semester'), 'Term')
        self.assertEqual(company.get_term_label('program'), 'Class/Section')
        self.assertEqual(company.get_term_label('academic_year'), 'Session')

    def test_04_k12_seed_profile(self):
        """K-12 School profile ships wired to the school terminology."""
        profile = self.profile_school
        self.assertEqual(profile.code, 'K12_SCHOOL')
        self.assertEqual(profile.institution_type, 'school')
        self.assertFalse(profile.is_legacy_university)
        self.assertEqual(profile.calendar_mode, 'term')
        self.assertEqual(profile.grading_scheme, 'simple_percentage')
        self.assertEqual(profile.terminology_profile_id, self.terminology_school)
        codes = profile.academic_unit_level_ids.mapped('code')
        self.assertEqual(codes, ['GRADE'])

    def test_05_label_summary_preview(self):
        """label_summary reflects the K-12 substitutions."""
        summary = self.terminology_school.label_summary
        self.assertIn('Class/Section', summary)
        self.assertIn('Term', summary)
        self.assertIn('Session', summary)
