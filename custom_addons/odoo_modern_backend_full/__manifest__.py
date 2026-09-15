# -*- coding: utf-8 -*-
{
    'name': 'Odoo Modern SaaS Backend UX',
    'version': '19.0.2.1.0',
    'category': 'Themes/Backend',
    'summary': 'Modern SaaS shell, OWL components, dashboards, dynamic sidebar and live theme customization for Odoo Community 19',
    'description': '''
A complete, non-invasive modern backend UX layer for Odoo Community 19.

Features:
- Modern application shell with dynamic responsive sidebar navigation
- Design-token based theme engine with runtime customization (Accents, Dark Mode, Density, Radius, Motion)
- Live Command Palette (Ctrl/Cmd + K) with fuzzy search across apps, menus, and actions
- SaaS dashboard framework with interactive period filtering, KPI metrics, chart primitive, activity timeline, and quick actions
- OWL component library and registry (ModernBadge, ModernStat, ModernEmptyState, ModernSectionHeader)
- Global list, form, kanban, chatter and control-panel modern styling
- Localized user preferences with instant local persistence without modifying Odoo core
''',
    'author': 'Antigravity / Odoo Dev',
    'license': 'LGPL-3',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'odoo_modern_backend_full/static/src/scss/tokens.scss',
            'odoo_modern_backend_full/static/src/scss/base.scss',
            'odoo_modern_backend_full/static/src/scss/shell.scss',
            'odoo_modern_backend_full/static/src/scss/components.scss',
            'odoo_modern_backend_full/static/src/scss/views.scss',
            'odoo_modern_backend_full/static/src/scss/apps.scss',
            'odoo_modern_backend_full/static/src/scss/dashboard.scss',
            'odoo_modern_backend_full/static/src/scss/responsive.scss',
            'odoo_modern_backend_full/static/src/xml/modern_backend.xml',
            'odoo_modern_backend_full/static/src/js/theme_service.js',
            'odoo_modern_backend_full/static/src/js/modern_shell.js',
            'odoo_modern_backend_full/static/src/js/command_palette.js',
            'odoo_modern_backend_full/static/src/js/theme_customizer.js',
            'odoo_modern_backend_full/static/src/js/systray.js',
            'odoo_modern_backend_full/static/src/js/dashboard.js',
            'odoo_modern_backend_full/static/src/js/component_registry.js',
        ],
    },
    'data': [
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
