{
    'name': 'UniCore Placement',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Placement Management',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['unicore_student'],
    'data': [
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'views/placement_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
