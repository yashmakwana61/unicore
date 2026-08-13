{
    'name': 'Oacis Student Skill Assessment',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student Skill Assessment System',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['oacis_student', 'oacis_faculty_profile'],
    'data': [
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'views/skill_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
