{
    'name': 'Edicai Academic Structure',
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
        'edicai_base',
        'edicai_campus',
        'edicai_security',
        'edicai_academic_generic',
        # Phase 1: is_legacy_institution reads company.institution_profile_id,
        # which is defined by edicai_institution_profile (standalone, no cycle).
        'edicai_institution_profile',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/edicai_program_type_data.xml',
        'views/edicai_faculty_views.xml',
        'views/edicai_department_views.xml',
        'views/edicai_program_views.xml',
        'views/edicai_specialisation_views.xml',
        'views/edicai_academic_kanban_views.xml',
        'menus/edicai_academic_menus.xml',
        'views/edicai_academic_view_mode_ext.xml',
        'views/edicai_academic_cleanup.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
