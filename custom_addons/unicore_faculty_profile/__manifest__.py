{
    'name': 'UniCore Faculty & Staff',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Faculty member and administrative staff profile management',
    'description': '''
        Manages faculty member and administrative staff
        profiles for UniCore ERP.
        Covers academic qualifications, publications,
        teaching workload, designations and contracts.
        Separate from unicore.faculty which is the
        academic organisational unit.
    ''',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base',
        'unicore_security',
        'unicore_campus',
        'unicore_academic',
        'unicore_calendar',
        'unicore_student',
    ],
    'data': [
        'security/unicore_faculty_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_faculty_sequence_data.xml',
        'views/unicore_faculty_qualification_views.xml',
        'views/unicore_faculty_publication_views.xml',
        'views/unicore_faculty_workload_views.xml',
        'views/unicore_staff_member_views.xml',
        'views/unicore_faculty_member_views.xml',
        'menus/unicore_faculty_profile_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
