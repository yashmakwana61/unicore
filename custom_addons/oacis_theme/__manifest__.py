{
    'name': 'Oacis Premium Theme',
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'summary': 'Enterprise-style premium backend theme for Oacis ERP',
    'description': """
Oacis Premium Theme transforms the Odoo CE backend into a polished,
professional interface inspired by Odoo Enterprise visual design.

Features:
- Enterprise-purple color system
- Inter/system font stack with proper type scale
- Redesigned navbar, sidebar and menus
- Polished form, list and kanban views
- Custom stat buttons and status badges
- Full Oacis analytics dashboard
- Mobile-responsive layout
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': ['web', 'mail', 'oacis_base'],
    'assets': {
        'web._assets_primary_variables': [
            (
                'before',
                'web/static/src/scss/primary_variables.scss',
                'oacis_theme/static/src/scss/primary_variables.scss',
            ),
        ],
        'web._assets_backend_helpers': [
            ('prepend', 'oacis_theme/static/src/scss/bootstrap_overridden.scss'),
        ],
        'web.assets_backend': [
            'oacis_theme/static/src/scss/variables.scss',
            'oacis_theme/static/src/scss/navbar.scss',
            'oacis_theme/static/src/scss/control_panel.scss',
            'oacis_theme/static/src/scss/list_view.scss',
            'oacis_theme/static/src/scss/kanban.scss',
            'oacis_theme/static/src/scss/chatter.scss',
            'oacis_theme/static/src/scss/dialogs.scss',
            'oacis_theme/static/src/scss/misc.scss',
            'oacis_theme/static/src/scss/apps_menu.scss',
            'oacis_theme/static/src/xml/apps_menu_patch.xml',
            'oacis_theme/static/src/js/apps_menu_patch.js',
            'oacis_theme/static/src/xml/apps_landing_screen.xml',
            'oacis_theme/static/src/js/apps_landing_screen.js',
            'oacis_theme/static/src/scss/apps_landing.scss',
        ],
    },
    'data': [
        'views/oacis_theme_templates.xml',
        'data/apps_landing_action.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
