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
        'security/oacis_groups.xml',
        'security/oacis_security.xml',
        'views/oacis_campus_views.xml',
        'views/res_company_views.xml',
        'menus/oacis_base_menus.xml',
        'views/oacis_base_view_mode_ext.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'oacis_base,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
