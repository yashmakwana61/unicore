"""Feature-toggle wiring tests (config activation).

Verifies ``res.company.has_feature`` / ``enabled_feature_codes`` and the
``ir.ui.menu._filter_visible_menus`` per-company gating: a company whose
profile lacks a feature loses that module's menus; UNI_LEGACY (all 13
features) and no-profile (legacy) hide nothing.

The menu-gating test uses a synthetic menu wired to the ``oacis_hostel``
module via ``ir.model.data`` so it stays self-contained (feature modules are
not install dependencies of this module's isolated test run).
"""

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisFeatureGatingTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.profile_legacy = cls.env.ref(
            'oacis_institution_profile.profile_university_legacy')
        cls.profile_school = cls.env.ref(
            'oacis_institution_profile.profile_school_k12')

    def test_01_has_feature_helper(self):
        """has_feature reflects the profile's toggles (legacy = all)."""
        self.company.institution_profile_id = self.profile_legacy.id
        self.assertTrue(self.company.has_feature('SCHOLARSHIP'))
        self.assertTrue(self.company.has_feature('HOSTEL'))
        self.assertTrue(self.company.has_feature('FEES'))

        self.company.institution_profile_id = self.profile_school.id
        self.assertFalse(self.company.has_feature('HOSTEL'))
        self.assertTrue(self.company.has_feature('SCHOLARSHIP'))

        self.company.institution_profile_id = False
        self.assertTrue(self.company.has_feature('HOSTEL'))

    def test_02_enabled_feature_codes_computed(self):
        """enabled_feature_codes lists the enabled codes (computed)."""
        self.company.institution_profile_id = self.profile_legacy.id
        codes = set(self.company.enabled_feature_codes.split(', '))
        self.assertIn('SCHOLARSHIP', codes)
        self.assertIn('HOSTEL', codes)

        self.company.institution_profile_id = self.profile_school.id
        codes = set(self.company.enabled_feature_codes.split(', '))
        self.assertNotIn('HOSTEL', codes)
        self.assertIn('SCHOLARSHIP', codes)

    def test_03_filter_visible_menus_gates_by_feature(self):
        """A feature-disabled company loses that module's menu; legacy keeps it."""
        action = self.env['ir.actions.act_window'].create({
            'name': 'Hostel Test Action',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
        })
        menu = self.env['ir.ui.menu'].create({
            'name': 'Hostel Test Menu',
            'parent_id': False,
            # ir.ui.menu.action is a Reference field -> "model,id" string.
            'action': 'ir.actions.act_window,%d' % action.id,
        })
        self.env['ir.model.data'].create({
            'module': 'oacis_hostel',
            'name': 'menu_hostel_test',
            'model': 'ir.ui.menu',
            'res_id': menu.id,
            'noupdate': True,
        })

        def visible():
            return self.env['ir.ui.menu'].search(
                [('id', '=', menu.id)])._filter_visible_menus()

        # UNI_LEGACY has HOSTEL -> visible.
        self.company.institution_profile_id = self.profile_legacy.id
        self.assertIn(menu, visible())

        # Profile without HOSTEL -> hidden.
        self.company.institution_profile_id = self.profile_school.id
        self.assertNotIn(menu, visible())

        # No profile = legacy -> visible.
        self.company.institution_profile_id = False
        self.assertIn(menu, visible())
