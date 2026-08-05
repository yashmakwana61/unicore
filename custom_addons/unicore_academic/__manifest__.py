{
    'name': 'UniCore Academic Structure',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Faculty, Department, Program and Specialisation management',
    'description': """
        Faculty, Department, Program and Specialisation management
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base',
        'unicore_campus',
        'unicore_security',
        'unicore_academic_generic',
        # Phase 1: is_legacy_institution reads company.institution_profile_id,
        # which is defined by unicore_institution_profile (standalone, no cycle).
        'unicore_institution_profile',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/unicore_program_type_data.xml',
        'views/unicore_faculty_views.xml',
        'views/unicore_department_views.xml',
        'views/unicore_program_views.xml',
        'views/unicore_specialisation_views.xml',
        'views/unicore_academic_kanban_views.xml',
        'menus/unicore_academic_menus.xml',
        'views/unicore_academic_view_mode_ext.xml',
        'views/unicore_academic_cleanup.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
