{
    'name': 'Oacis Design',
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'summary': 'Dynamic backend theme configuration engine for Oacis',
    'description': """
Oacis Design theme configuration engine for Odoo 19.
Allows company-wide default styling and per-user overrides for:
- Font Family (System, Inter, Roboto, Outfit)
- List Density (Default, Comfortable, Compact)
- Border Radius (None, Small, Medium, Large)
- Chatter Position (Bottom, Side)
- Start Menu Background (per-company) and per-user pinned (favourite) apps
    """,
    'depends': ['base', 'web', 'mail', 'base_setup'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'oacis_design/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
