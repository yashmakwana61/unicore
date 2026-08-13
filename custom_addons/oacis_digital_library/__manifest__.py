{
    'name': 'Oacis Digital Library',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Digital Library Materials',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['oacis_student', 'oacis_library'],
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
