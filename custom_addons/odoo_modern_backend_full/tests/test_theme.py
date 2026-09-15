# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.modules.module import get_module_path, get_manifest
import os


@tagged('post_install', '-at_install')
class TestModernBackendFull(TransactionCase):

    def setUp(self):
        super().setUp()
        self.module_name = 'odoo_modern_backend_full'

    def test_01_module_installed(self):
        """Test that the module is installed in the database."""
        module = self.env['ir.module.module'].search([('name', '=', self.module_name)])
        self.assertTrue(module.exists(), "Module record should exist in ir.module.module")
        self.assertEqual(module.state, 'installed', "Module should be in installed state")

    def test_02_dashboard_client_action(self):
        """Test that the dashboard client action is registered with correct tag."""
        action = self.env.ref(f'{self.module_name}.action_modern_dashboard', raise_if_not_found=False)
        self.assertTrue(action, "action_modern_dashboard XML ID should resolve")
        self.assertEqual(action._name, 'ir.actions.client')
        self.assertEqual(action.tag, 'odoo_modern_backend.dashboard')
        self.assertEqual(action.name, 'Modern Dashboard')

    def test_03_dashboard_menu(self):
        """Test that the dashboard menu item exists and links to the client action."""
        menu = self.env.ref(f'{self.module_name}.menu_modern_dashboard', raise_if_not_found=False)
        self.assertTrue(menu, "menu_modern_dashboard XML ID should resolve")
        self.assertEqual(menu.name, 'Modern Dashboard')
        action = self.env.ref(f'{self.module_name}.action_modern_dashboard')
        self.assertEqual(menu.action, action, "Menu item should link to action_modern_dashboard")

    def test_04_manifest_assets_exist(self):
        """Test that all static assets referenced in manifest actually exist on disk."""
        mod_path = get_module_path(self.module_name)
        self.assertTrue(mod_path and os.path.isdir(mod_path), f"Module path {mod_path} must exist")

        manifest_data = get_manifest(self.module_name)
        assets_backend = manifest_data.get('assets', {}).get('web.assets_backend', [])
        self.assertTrue(len(assets_backend) > 0, "web.assets_backend should have asset entries")

        for asset_path in assets_backend:
            # Strip module prefix
            if asset_path.startswith(f'{self.module_name}/'):
                rel_path = asset_path[len(self.module_name) + 1:]
                disk_path = os.path.join(mod_path, *rel_path.split('/'))
                self.assertTrue(
                    os.path.exists(disk_path),
                    f"Asset path {asset_path} resolved to {disk_path} which does not exist!"
                )

    def test_05_xml_templates_content(self):
        """Test that modern_backend.xml contains all expected QWeb templates."""
        mod_path = get_module_path(self.module_name)
        xml_path = os.path.join(mod_path, 'static', 'src', 'xml', 'modern_backend.xml')
        self.assertTrue(os.path.exists(xml_path), "modern_backend.xml must exist")

        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        expected_templates = [
            'odoo_modern_backend.ModernShell',
            'odoo_modern_backend.CommandPalette',
            'odoo_modern_backend.ThemeCustomizer',
            'odoo_modern_backend.ModernThemeSystray',
            'odoo_modern_backend.ModernDashboard',
            'odoo_modern_backend.KPI',
            'odoo_modern_backend.ProgressCard',
            'odoo_modern_backend.ActivityCard',
            'odoo_modern_backend.QuickAction',
            'odoo_modern_backend.ModernBadge',
            'odoo_modern_backend.ModernStat',
            'odoo_modern_backend.ModernEmptyState',
            'odoo_modern_backend.ModernSectionHeader',
        ]

        for tmpl in expected_templates:
            self.assertIn(
                f't-name="{tmpl}"',
                xml_content,
                f"Template {tmpl} must be present in modern_backend.xml"
            )
