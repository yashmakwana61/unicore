{
    'name': 'Edicai Digital Library',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Digital Library Materials',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['edicai_student', 'edicai_library'],
    'data': [
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'views/digital_library_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
