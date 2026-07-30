{
    'name': 'UniCore Premium Theme',
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'summary': 'Enterprise-style premium backend theme for UniCore ERP',
    'description': """
UniCore Premium Theme transforms the Odoo CE backend into a polished,
professional interface inspired by Odoo Enterprise visual design.

Features:
- Enterprise-purple color system
- Inter/system font stack with proper type scale
- Redesigned navbar, sidebar and menus
- Polished form, list and kanban views
- Custom stat buttons and status badges
- Full UniCore analytics dashboard
- Mobile-responsive layout
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': ['web', 'mail', 'unicore_base'],
    'assets': {
        'web._assets_primary_variables': [
            (
                'before',
                'web/static/src/scss/primary_variables.scss',
                'unicore_theme/static/src/scss/primary_variables.scss'
            ),
        ],
        'web._assets_backend_helpers': [
            ('prepend', 'unicore_theme/static/src/scss/bootstrap_overridden.scss'),
        ],
        'web.assets_backend': [
            'unicore_theme/static/src/scss/variables.scss',
            'unicore_theme/static/src/scss/navbar.scss',
            'unicore_theme/static/src/scss/control_panel.scss',
            'unicore_theme/static/src/scss/list_view.scss',
            'unicore_theme/static/src/scss/kanban.scss',
            'unicore_theme/static/src/scss/chatter.scss',
            'unicore_theme/static/src/scss/dialogs.scss',
            'unicore_theme/static/src/scss/misc.scss',
            'unicore_theme/static/src/scss/apps_menu.scss',
            'unicore_theme/static/src/xml/apps_menu_patch.xml',
            'unicore_theme/static/src/js/apps_menu_patch.js',
            'unicore_theme/static/src/xml/apps_landing_screen.xml',
            'unicore_theme/static/src/js/apps_landing_screen.js',
            'unicore_theme/static/src/scss/apps_landing.scss',
        ],
    },
    'data': [
        'views/unicore_theme_templates.xml',
        'data/apps_landing_action.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
