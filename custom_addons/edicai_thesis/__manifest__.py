{
    'name': 'Edicai Thesis',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Thesis Management',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['edicai_student', 'edicai_faculty_profile'],
    'data': [
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'views/thesis_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
