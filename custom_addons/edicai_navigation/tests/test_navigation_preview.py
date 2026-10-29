# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged

from ..models.navigation_preview import MANIFEST_REPARENTS, WORKSPACE_XMLIDS


@tagged('post_install', '-at_install')
class TestNavigationPreview(TransactionCase):

    def setUp(self):
        super().setUp()
        self.util = self.env['navigation.preview.util'].sudo()

    def test_workspace_roots_ship_inactive(self):
        for xid in WORKSPACE_XMLIDS:
            self.assertFalse(
                self.env.ref(xid).sudo().active,
                '%s must ship inactive (preview off by default)' % xid)

    def test_manifest_rows_resolve(self):
        missing = self.util._validate_missing()
        self.assertFalse(
            missing.get('menu'), 'all manifest menus must exist: %s' % missing)
        self.assertFalse(
            missing.get('workspace'), 'all workspace xmlids must exist: %s' % missing)

    def test_enable_disable_roundtrip(self):
        orig = {}
        IMD = self.env['ir.model.data'].sudo()
        for xid, _dest, _seq in MANIFEST_REPARENTS:
            menu = self.env.ref(xid).sudo()
            data = IMD.search([('model', '=', 'ir.ui.menu'),
                               ('res_id', '=', menu.parent_id.id)], limit=1)
            orig[xid] = ('%s.%s' % (data.module, data.name) if data else '',
                         menu.sequence)
        res_on = self.util.enable_preview()
        self.assertTrue(res_on.get('ok'), 'enable must succeed: %s' % res_on)
        for xid, dest, _seq in MANIFEST_REPARENTS:
            menu = self.env.ref(xid).sudo()
            dest_menu = self.env.ref(dest).sudo()
            self.assertEqual(menu.parent_id.id, dest_menu.id,
                             '%s must be reparented under %s' % (xid, dest))
        for xid in WORKSPACE_XMLIDS:
            self.assertTrue(self.env.ref(xid).sudo().active,
                            '%s must go active when preview is on' % xid)
        res_off = self.util.disable_preview()
        self.assertTrue(res_off.get('ok'), 'disable must succeed: %s' % res_off)
        for xid, (old_parent_xmlid, old_seq) in orig.items():
            menu = self.env.ref(xid).sudo()
            data = IMD.search([('model', '=', 'ir.ui.menu'),
                               ('res_id', '=', menu.parent_id.id)], limit=1)
            restored = '%s.%s' % (data.module, data.name) if data else ''
            self.assertEqual(restored, old_parent_xmlid,
                             '%s must be restored to parent %s' % (xid, old_parent_xmlid))
            self.assertEqual(menu.sequence, old_seq,
                             '%s sequence must be restored' % xid)
        for xid in WORKSPACE_XMLIDS:
            self.assertFalse(self.env.ref(xid).sudo().active,
                             '%s must vanish (inactive) after disable' % xid)

    def test_no_duplicate_menus_created(self):
        count_before = self.env['ir.ui.menu'].sudo().search_count([])
        self.util.enable_preview()
        self.util.disable_preview()
        count_after = self.env['ir.ui.menu'].sudo().search_count([])
        self.assertEqual(count_before, count_after,
                         'toggle must not create or delete menu records')

    def test_role_visibility_admin(self):
        # In Odoo, menu visibility follows record accessibility: grouping menus
        # whose actions target models the user cannot read are hidden. The
        # Super Admin role profile therefore holds ALL edicai functional
        # groups (see role_navigation_matrix.csv). The API group is added
        # here as a test fixture (rolled back; no production change).
        admin = self.env.ref('base.user_admin')
        api_admin_group = self.env.ref('edicai_api.group_edicai_api_admin')
        admin.group_ids = [(4, api_admin_group.id)]
        self.util.enable_preview()
        visible = self.env['ir.ui.menu'].with_user(admin)._visible_menu_ids()
        for xid in WORKSPACE_XMLIDS:
            root = self.env.ref(xid)
            self.assertIn(root.id, visible,
                          '%s must be visible to admin when preview is on' % xid)
        # Data-security coupling: WITHOUT the api group the admin would not
        # see Workspace 110 — demonstrating that visibility follows access.
        admin.group_ids = [(3, api_admin_group.id)]
        visible = self.env['ir.ui.menu'].with_user(admin)._visible_menu_ids()
        root110 = self.env.ref('edicai_navigation.menu_workspace_110')
        self.assertNotIn(
            root110.id, visible,
            'Workspace 110 must stay hidden without API record access')
        self.util.disable_preview()
        visible = self.env['ir.ui.menu'].with_user(admin)._visible_menu_ids()
        for xid in WORKSPACE_XMLIDS:
            root = self.env.ref(xid, raise_if_not_found=False)
            if root:
                self.assertNotIn(
                    root.id, visible,
                    '%s must be invisible to admin when preview is off' % xid)

    def test_role_visibility_plain_user(self):
        """A plain internal user (no edicai roles) must NOT see workspaces."""
        self.util.enable_preview()
        user = self.env['res.users'].sudo().create({
            'name': 'Nav Visibility Test',
            'login': 'nav_visibility_test',
            'email': 'nav_visibility_test@example.invalid',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        visible = self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
        for xid in WORKSPACE_XMLIDS:
            root = self.env.ref(xid)
            self.assertNotIn(root.id, visible,
                             '%s must NOT be visible to plain users' % xid)
