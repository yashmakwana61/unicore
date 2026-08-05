"""Gap-2: terminology-aware view labels (get_view rewrite).

The ``ir.ui.view.get_view`` override lives in unicore_institution_profile;
these tests verify the runtime label rewriting using real UniCore models
available in this module's dependency graph (student / enrollment / offering).
"""

from odoo.tests import TransactionCase, tagged


@tagged('unicore', 'unit')
class TestTerminologyViews(TransactionCase):
    """Verify view field labels are rewritten per the terminology profile."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

    def _make_school_profile(self):
        """Attach a K-12 school profile carrying a terminology profile."""
        term = self.env['unicore.terminology.profile'].create({
            'name': 'K12 Term Test',
            'code': 'K12TERM',
            'term_program': 'Class/Section',
            'term_student': 'Learner',
            'term_semester': 'Term',
            'term_academic_year': 'Session',
        })
        self.company.institution_profile_id = self.env[
            'unicore.institution.profile'
        ].create({
            'name': 'K12 School Test',
            'code': 'K12SCH',
            'institution_type': 'school',
            'is_legacy_university': False,
            'terminology_profile_id': term.id,
        }).id

    def _render(self, model, arch):
        view = self.env['ir.ui.view'].create({
            'name': 'test-term-view-%s' % model,
            'model': model,
            'arch': arch,
        })
        result = self.env['ir.ui.view'].get_view(
            view_id=view.id, view_type='form')
        return result['arch']

    def test_01_no_profile_arch_unchanged(self):
        """Legacy companies get a byte-identical architecture."""
        self.company.institution_profile_id = False
        arch = self._render(
            'unicore.enrollment',
            '<form>'
            '<field name="student_id" string="Student"/>'
            '<field name="semester_id" string="Semester"/>'
            '</form>')
        self.assertIn('string="Student"', arch)
        self.assertIn('string="Semester"', arch)
        self.assertNotIn('string="Learner"', arch)
        self.assertNotIn('string="Term"', arch)

    def test_02_k12_profile_rewrites_enrollment(self):
        """K-12 rewrites Student -> Learner and Semester -> Term."""
        self._make_school_profile()
        arch = self._render(
            'unicore.enrollment',
            '<form>'
            '<field name="student_id" string="Student"/>'
            '<field name="semester_id" string="Semester"/>'
            '</form>')
        self.assertIn('string="Learner"', arch)
        self.assertIn('string="Term"', arch)
        self.assertNotIn('string="Student"', arch)
        self.assertNotIn('string="Semester"', arch)

    def test_03_k12_profile_program_label(self):
        """K-12 rewrites Program -> Class/Section on whitelisted models."""
        self._make_school_profile()
        arch = self._render(
            'unicore.student',
            '<form><field name="program_id" string="Program"/></form>')
        self.assertIn('string="Class/Section"', arch)
        self.assertNotIn('string="Program"', arch)

    def test_04_non_whitelisted_model_untouched(self):
        """Models outside the whitelist are never rewritten."""
        self._make_school_profile()
        arch = self._render(
            'unicore.course.offering',
            '<form><field name="program_id" string="Program"/></form>')
        self.assertIn('string="Program"', arch)
        self.assertNotIn('string="Class/Section"', arch)
