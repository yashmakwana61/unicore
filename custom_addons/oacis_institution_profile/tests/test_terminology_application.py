"""Terminology application: global field-label + view-arch relabeling.

Attaching a NON-legacy institution profile (e.g. TRN Training Institute, K-12
School) must relabel the labels served to the web client EVERYWHERE — on every
model's fields (via the 'base' ``fields_get`` hook) and in view architectures
(filters, groupby labels via the ``ir.ui.view.get_view`` hook). No profile /
legacy profile must stay byte-identical.

The isolated run only loads oacis_institution_profile + its dependencies, so
the primary assertions target ``oacis.terminology.profile`` (defined in this
module, whose field labels literally carry the university terms: "Program
Label", "Student Label", ...). When the broader Oacis modules are installed
(full-suite run), the same assertions repeat on ``oacis.program`` /
``oacis.enrollment`` to prove the relabeling truly reaches unrelated modules;
those assertions skip cleanly when the model is not in the registry.
"""

import uuid

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisTerminologyApplicationTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # The Oacis application menu (root + Academic Structure) is restricted
        # to the Staff group. The test framework's default env is the superuser,
        # which holds no groups, so menus are invisible to it. Create a real
        # staff user to exercise the menu relabeling exactly like a browser user.
        staff_group = cls.env.ref(
            'oacis_base.group_oacis_staff', raise_if_not_found=False)
        cls.staff_user = None
        if staff_group:
            cls.staff_user = cls.env['res.users'].create({
                'name': 'Oacis Staff Tester',
                'login': 'oacis_staff_tester_%s' % uuid.uuid4().hex[:8],
                'group_ids': [(6, 0, [staff_group.id])],
            })

    def _attach(self, xmlid):
        self.company.institution_profile_id = \
            self.env.ref('oacis_institution_profile.%s' % xmlid).id

    def _relabel(self, model, field_names):
        """fields_get on the model, skipping when the model is not installed."""
        if model not in self.env.registry:
            self.skipTest('model %s not installed in this run' % model)
        return self.env[model].fields_get(field_names)

    def test_01_no_profile_stays_generic(self):
        """No profile -> field labels stay generic (byte-identical path)."""
        self.company.institution_profile_id = False
        fields = self._relabel('oacis.terminology.profile',
                               ['term_program', 'term_student'])
        self.assertEqual(fields['term_program']['string'], 'Program Label')
        self.assertEqual(fields['term_student']['string'], 'Student Label')

    def test_02_training_relabels_fields_everywhere(self):
        """TRN attached -> fields_get relabels across models."""
        self._attach('profile_training_institute')
        # Same-module model (always available): the terminology profile's own
        # field labels carry the university terms and must be rewritten.
        fields = self._relabel('oacis.terminology.profile', [
            'term_program', 'term_department', 'term_student', 'term_semester',
            'term_faculty', 'term_faculty_staff', 'term_academic_year',
        ])
        self.assertEqual(fields['term_program']['string'], 'Course Label')
        self.assertEqual(fields['term_department']['string'], 'Module Label')
        self.assertEqual(fields['term_student']['string'], 'Trainee Label')
        self.assertEqual(fields['term_semester']['string'], 'Cycle Label')
        self.assertEqual(fields['term_academic_year']['string'], 'Year Label')
        self.assertEqual(fields['term_faculty_staff']['string'],
                         'Trainer Label')
        # Faculty is NOT relabeled by TRN -> untouched (no spurious rewrite).
        self.assertEqual(fields['term_faculty']['string'], 'Faculty Label')

        # Cross-module proof (full-suite run only).
        fields = self._relabel('oacis.enrollment',
                               ['student_id', 'semester_id'])
        self.assertEqual(fields['student_id']['string'], 'Trainee')
        self.assertEqual(fields['semester_id']['string'], 'Cycle')
        fields = self._relabel('oacis.program',
                               ['name', 'code', 'department_id', 'faculty_id'])
        self.assertEqual(fields['name']['string'], 'Course Name')
        self.assertEqual(fields['code']['string'], 'Course Code')
        self.assertEqual(fields['department_id']['string'], 'Module')
        self.assertEqual(fields['faculty_id']['string'], 'Faculty')

    def test_03_training_relabels_view_arch(self):
        """TRN attached -> search filter / groupby labels relabel."""
        view = self.env.ref(
            'oacis_academic.oacis_program_search_view',
            raise_if_not_found=False)
        if not view:
            self.skipTest('oacis_academic module not installed')
        self._attach('profile_training_institute')
        arch = self.env['ir.ui.view'].get_view(view.id, 'search')['arch']
        self.assertIn('string="Module"', arch)          # was Department
        self.assertIn('string="Course Type"', arch)     # was Program Type
        self.assertIn('string="Active Courses"', arch)  # was Active Programs
        # untouched labels must survive
        self.assertIn('string="Faculty"', arch)
        self.assertIn('string="Academic Unit"', arch)

    def test_04_k12_relabels_fields(self):
        """K-12 attached -> department 'Grade Level', program 'Class/Section'."""
        self._attach('profile_school_k12')
        fields = self._relabel('oacis.terminology.profile',
                               ['term_program', 'term_department'])
        self.assertEqual(fields['term_program']['string'], 'Class/Section Label')
        self.assertEqual(fields['term_department']['string'],
                         'Grade Level Label')
        fields = self._relabel('oacis.program', ['name', 'department_id'])
        self.assertEqual(fields['name']['string'], 'Class/Section Name')
        self.assertEqual(fields['department_id']['string'], 'Grade Level')

    def test_05_training_relabels_menus(self):
        """TRN attached -> navigation menu labels relabel, detach restores."""
        menu = self.env.ref(
            'oacis_academic.menu_oacis_program_list',
            raise_if_not_found=False)
        if not menu:
            self.skipTest('oacis_academic module not installed')
        if not self.staff_user:
            self.skipTest('oacis_base.group_oacis_staff not available')
        self._attach('profile_training_institute')
        staff_env = self.env(user=self.staff_user.id)

        def _menu_names():
            return [
                m['name']
                for m in staff_env['ir.ui.menu'].load_menus(False).values()
                if isinstance(m, dict) and m.get('name')
            ]

        names = _menu_names()
        root = self.env.ref('oacis_base.menu_oacis_root',
                            raise_if_not_found=False)
        if root:
            # Staff user must see the app root menu. Its NAME differs by DB
            # ('Oacis' on fresh DBs, 'SIS' on the migrated live DB), so match
            # by record id instead of hardcoding a name.
            self.assertIn(
                root.id,
                staff_env['ir.ui.menu'].load_menus(False),
                'staff user must see the Oacis/SIS app root',
            )
        self.assertIn('Courses', names)       # Programs relabeled
        self.assertIn('Modules', names)       # Departments relabeled
        self.assertNotIn('Programs', names)
        self.assertNotIn('Departments', names)
        # Detach -> generic labels restored.
        self.company.institution_profile_id = False
        names = _menu_names()
        self.assertIn('Programs', names)
        self.assertIn('Departments', names)

    def test_06_training_relabels_action_title(self):
        """TRN attached -> action name (page title) relabeled."""
        action = self.env.ref(
            'oacis_academic.action_oacis_program',
            raise_if_not_found=False)
        if not action:
            self.skipTest('oacis_academic module not installed')
        self._attach('profile_training_institute')
        self.assertEqual(action._get_action_dict()['name'], 'Courses')
        self.company.institution_profile_id = False
        self.assertEqual(action._get_action_dict()['name'], 'Programs')
