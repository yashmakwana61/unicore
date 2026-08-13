{
    'name': 'Oacis Progression',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student Progression Management',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['oacis_student', 'oacis_grading', 'oacis_attendance', 'oacis_curriculum'],
    'data': [
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'views/progression_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
