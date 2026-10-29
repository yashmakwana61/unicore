# -*- coding: utf-8 -*-
{
    'name': 'Edicai Navigation UI',
    'version': '19.0.1.0.0',
    'category': 'Education/Navigation',
    'summary': 'Minimal line icons, accordion sidebar, top-bar Calendar/Settings buttons',
    'description': """
Phase 2/3 of the navigation redesign, isolated from module data logic:
- `web_icon` line-icon set (transparent, 1.5 stroke) for the sidebar app
  entries: Home, the 11 Edicai workspaces, Website and Apps.
- AppsBar accordion: workspace roots expand their first-level sections with a
  rotating chevron (150ms, reduced-motion aware).
- Top-bar buttons beside the profile cluster: Calendar (opens
  `calendar.action_calendar_event`, internal users) and Settings
  (`base_setup.action_general_configuration`, admins only) — both using
  transparent line glyphs, as those apps are hidden from the sidebar while the
  navigation preview is ON.
- No Odoo core modification; muk_web_theme/muk_web_appsbar are patched by
  template/proprototype extension only.
""",
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'license': 'OPL-1',
    'depends': [
        'web', 'calendar',
        'edicai_base', 'edicai_home', 'edicai_navigation',
    ],
    'data': [
        'data/navigation_icons.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edicai_nav_ui/static/src/scss/edicai_nav_ui.scss',
            'edicai_nav_ui/static/src/xml/edicai_nav_ui.xml',
            'edicai_nav_ui/static/src/js/appsbar_accordion.js',
            'edicai_nav_ui/static/src/js/topbar_buttons.js',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
