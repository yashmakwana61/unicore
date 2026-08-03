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
        'security/unicore_groups.xml',
        'security/unicore_security.xml',
        'views/unicore_campus_views.xml',
        'views/res_company_views.xml',
        'menus/unicore_base_menus.xml',
        'views/unicore_base_view_mode_ext.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_base,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
