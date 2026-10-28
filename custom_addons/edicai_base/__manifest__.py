{
    'name': 'SIS',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Base module for Education Management Suite',
    'description': """
        Base module for Education Management Suite
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'security/edicai_groups.xml',
        'security/edicai_security.xml',
        'views/edicai_campus_views.xml',
        'views/res_company_views.xml',
        'views/edicai_overview_dashboard_views.xml',
        'menus/edicai_base_menus.xml',
        'views/edicai_base_view_mode_ext.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('include', 'web.chartjs_lib'),
            'edicai_base/static/src/scss/edicai_overview_dashboard.scss',
            'edicai_base/static/src/xml/edicai_overview_dashboard.xml',
            'edicai_base/static/src/js/edicai_overview_dashboard.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'web_icon': 'edicai_base,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
