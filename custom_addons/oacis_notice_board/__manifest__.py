{
    'name': 'Oacis Notice Board',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Persistent circulars and notices for students, faculty and guardians',
    'description': '''
        Oacis Notice Board provides a persistent bulletin board for
        institutional circulars and notices that can be browsed by
        students, faculty and guardians through the portal experience.
    ''',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'mail',
        'oacis_base',
        'oacis_security',
        'oacis_student',
        'oacis_faculty_profile',
        'oacis_guardian',
        'oacis_academic',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/oacis_notice_views.xml',
        'menus/oacis_notice_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
