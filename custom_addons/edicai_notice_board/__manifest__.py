{
    'name': 'Edicai Notice Board',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Persistent circulars and notices for students, faculty and guardians',
    'description': '''
        Edicai Notice Board provides a persistent bulletin board for
        institutional circulars and notices that can be browsed by
        students, faculty and guardians through the portal experience.
    ''',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'mail',
        'edicai_base',
        'edicai_security',
        'edicai_student',
        'edicai_faculty_profile',
        'edicai_guardian',
        'edicai_academic',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/edicai_notice_views.xml',
        'views/edicai_notice_portal_templates.xml',
        'menus/edicai_notice_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
