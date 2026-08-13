{
    'name': 'UniCore Notice Board',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Persistent circulars and notices for students, faculty and guardians',
    'description': '''
        UniCore Notice Board provides a persistent bulletin board for
        institutional circulars and notices that can be browsed by
        students, faculty and guardians through the portal experience.
    ''',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'mail',
        'unicore_base',
        'unicore_security',
        'unicore_student',
        'unicore_faculty_profile',
        'unicore_guardian',
        'unicore_academic',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/unicore_notice_views.xml',
        'menus/unicore_notice_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
