# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNavigationPreview(TransactionCase):

    def setUp(self):
        super().setUp()
        self.util = self.env['navigation.preview.util'].sudo()

    def test_workspace_roots_inactive_by_default(self):
        for xid in self.util.WORKSPACE_XMLIDS:
            root = self.env.ref(xid)
            self.assertFalse(root.active, f'{xid} must ship inactive')

    def test_manifest_rows_resolve(self):
        missing = self.util._validate_missing()
        self.assertFalse(missing.get('menu'), 'all manifest menus must exist')
        self.assertFalse(missing.get('workspace'), 'all workspace xmlids must exist')

    def test_enable_disable_roundtrip(self):
        before = {xid: (m.parent_id.id, m.sequence)
                  for xid, m in
                  ((x, self.env.ref(x).sudo())
                   for x, _d, _s in self.util.MANIFEST_REPARENTS)}
        res_on = self.util.enable_preview()
        self.assertTrue(res_on['ok'])
        for xid, dest, _seq in self.util.MANIFEST_REPARENTS:
            menu = self.env.ref(xid).sudo()
            dest_menu = self.env.ref(dest).sudo()
            self.assertEqual(menu.parent_id.id, dest_menu.id,
                             f'{xid} must be reparented under {dest}')
        for xid in self.util.WORKSPACE_XMLIDS:
            self.assertTrue(self.env.ref(xid).sudo().active)
        res_off = self.util.disable_preview()
        self.assertTrue(res_off['ok'])
        for xid, (old_parent, old_seq) in before.items():
            menu = self.env.ref(xid).sudo()
            self.assertEqual(menu.parent_id.id, old_parent,
                             f'{xid} must be restored to its original parent')
            self.assertEqual(menu.sequence, old_seq)
        for xid in self.util.WORKSPACE_XMLIDS:
            self.assertFalse(self.env.ref(xid).sudo().active)

    def test_no_duplicate_menus_created(self):
        count_before = self.env['ir.ui.menu'].sudo().search_count([])
        self.util.enable_preview()
        self.util.disable_preview()
        count_after = self.env['ir.ui.menu'].sudo().search_count([])
        self.assertEqual(count_before, count_after,
                         'toggle must not create or delete menu records')

    def test_role_visibility_admin_sees_all(self):
        self.util.enable_preview()
        Admin = self.env.ref('base.user_admin').sudo()
        admin_env = self.env(user=Admin.id)
        menus = self.env['ir.ui.menu'].with_user(Admin).sudo(False)
        visible = admin_env._visible_menu_ids()
        for xid in self.util.WORKSPACE_XMLIDS:
            root = self.env.ref(xid)
            self.assertIn(root.id, visible,
                          f'{xid} must be visible to system admin when preview on')
        self.util.disable_preview()
        visible = admin_env._visible_menu_ids()
        for xid in self.util.WORKSPACE_XMLIDS:
            root = self.env.ref(xid)
            self.assertNotIn(root.id, visible,
                             f'{xid} must vanish when preview is off')
