"""Ready-to-attach institution profile templates (Phase 5 catalog).

Verifies that each seeded template (College / Training Institute / Academy /
Coaching Center) carries its full related settings: institution_type,
calendar_mode, effective grading scheme, academic unit levels, terminology
profile and feature toggles. UNI_LEGACY and K12_SCHOOL are covered elsewhere.
"""

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'unit')
class UniCoreProfileTemplateTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

    def _profile(self, xmlid):
        return self.env.ref('unicore_institution_profile.%s' % xmlid)

    def _unit_codes(self, profile):
        return sorted(profile.academic_unit_level_ids.mapped('code'))

    def test_01_college_profile_wiring(self):
        """College: semester, credit GPA, FAC/DEP/STREAM levels, all features."""
        profile = self._profile('profile_college')
        self.assertEqual(profile.code, 'COL')
        self.assertEqual(profile.institution_type, 'college')
        self.assertFalse(profile.is_legacy_university)
        self.assertEqual(profile.calendar_mode, 'semester')
        self.assertEqual(profile.effective_grading_scheme, 'credit_gpa')
        self.assertEqual(profile.grading_scheme_id.code, 'CREDIT_GPA')
        self.assertEqual(self._unit_codes(profile), ['DEP', 'FAC', 'STREAM'])
        terminology = profile.terminology_profile_id
        self.assertEqual(terminology.code, 'COL')
        self.assertEqual(terminology.resolve_label('program'), 'Degree Program')
        self.assertEqual(terminology.resolve_label('faculty'), 'Faculty')
        self.assertEqual(terminology.resolve_label('semester'), 'Semester')
        # A college keeps the full university feature set.
        self.assertTrue(profile.feature_toggle_ids.filtered(
            lambda f: f.code == 'HOSTEL'))
        self.assertTrue(profile.feature_toggle_ids.filtered(
            lambda f: f.code == 'CONVOCATION'))

    def test_02_training_profile_wiring(self):
        """Training: rolling-batch, simple percentage, BATCH/OTHER, trainee."""
        profile = self._profile('profile_training_institute')
        self.assertEqual(profile.code, 'TRN')
        self.assertEqual(profile.institution_type, 'training')
        self.assertFalse(profile.is_legacy_university)
        self.assertEqual(profile.calendar_mode, 'rolling_batch')
        self.assertEqual(profile.effective_grading_scheme, 'simple_percentage')
        self.assertEqual(profile.grading_scheme_id.code, 'SIMPLE_PCT')
        self.assertEqual(self._unit_codes(profile), ['BATCH', 'OTHER'])
        terminology = profile.terminology_profile_id
        self.assertEqual(terminology.code, 'TRN')
        self.assertEqual(terminology.resolve_label('student'), 'Trainee')
        self.assertEqual(terminology.resolve_label('faculty_staff'), 'Trainer')
        self.assertEqual(terminology.resolve_label('semester'), 'Cycle')
        # Faculty concept is hidden (blank term) for training institutes.
        self.assertFalse(terminology.term_faculty)
        # Feature subset: fees/admission on, hostel/convocation off.
        self.assertTrue(profile.feature_toggle_ids.filtered(
            lambda f: f.code == 'FEES'))
        self.assertFalse(profile.feature_toggle_ids.filtered(
            lambda f: f.code == 'HOSTEL'))

    def test_03_academy_profile_wiring(self):
        """Academy / Test-Prep: term calendar, pass/fail, GRADE+BATCH/OTHER."""
        profile = self._profile('profile_academy')
        self.assertEqual(profile.code, 'ACA')
        self.assertEqual(profile.institution_type, 'academy')
        self.assertFalse(profile.is_legacy_university)
        self.assertEqual(profile.calendar_mode, 'term')
        self.assertEqual(profile.effective_grading_scheme, 'pass_fail')
        self.assertEqual(profile.grading_scheme_id.code, 'PASS_FAIL')
        self.assertEqual(self._unit_codes(profile), ['BATCH', 'GRADE', 'OTHER'])
        terminology = profile.terminology_profile_id
        self.assertEqual(terminology.code, 'ACA')
        self.assertEqual(terminology.resolve_label('faculty_staff'), 'Instructor')
        self.assertEqual(terminology.resolve_label('semester'), 'Term')
        self.assertEqual(terminology.resolve_label('academic_year'), 'Session')

    def test_04_coaching_profile_wiring(self):
        """Coaching Center: rolling-batch, certificate grading, coach/cycle."""
        profile = self._profile('profile_coaching_center')
        self.assertEqual(profile.code, 'COA')
        self.assertEqual(profile.institution_type, 'coaching')
        self.assertFalse(profile.is_legacy_university)
        self.assertEqual(profile.calendar_mode, 'rolling_batch')
        self.assertEqual(profile.effective_grading_scheme, 'certificate_only')
        self.assertEqual(profile.grading_scheme_id.code, 'CERT_ONLY')
        self.assertEqual(self._unit_codes(profile), ['BATCH', 'OTHER'])
        terminology = profile.terminology_profile_id
        self.assertEqual(terminology.code, 'COA')
        self.assertEqual(terminology.resolve_label('faculty_staff'), 'Coach')
        self.assertEqual(terminology.resolve_label('semester'), 'Cycle')
        self.assertFalse(terminology.term_faculty)

    def test_05_company_attachment_effect(self):
        """Attaching a template drives terminology + feature gating live."""
        profile = self._profile('profile_training_institute')
        self.company.institution_profile_id = profile.id
        # Terminology follows the profile.
        self.assertEqual(self.company.get_term_label('student'), 'Trainee')
        # Feature gating reflects the template's toggle subset.
        self.assertTrue(self.company.has_feature('FEES'))
        self.assertTrue(self.company.has_feature('ADMISSION'))
        self.assertFalse(self.company.has_feature('HOSTEL'))
        self.assertFalse(self.company.has_feature('CONVOCATION'))
        enabled = set(self.company.enabled_feature_codes.split(', '))
        self.assertIn('FEES', enabled)
        self.assertNotIn('HOSTEL', enabled)
        # Detaching restores legacy university defaults.
        self.company.institution_profile_id = False
        self.assertEqual(self.company.get_term_label('student'), None)
        self.assertTrue(self.company.has_feature('HOSTEL'))
