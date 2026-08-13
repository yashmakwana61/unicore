{
    'name': 'Oacis Academic Structure',
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
        'oacis_base',
        'oacis_campus',
        'oacis_security',
        'oacis_academic_generic',
        # Phase 1: is_legacy_institution reads company.institution_profile_id,
        # which is defined by oacis_institution_profile (standalone, no cycle).
        'oacis_institution_profile',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/oacis_program_type_data.xml',
        'views/oacis_faculty_views.xml',
        'views/oacis_department_views.xml',
        'views/oacis_program_views.xml',
        'views/oacis_specialisation_views.xml',
        'views/oacis_academic_kanban_views.xml',
        'menus/oacis_academic_menus.xml',
        'views/oacis_academic_view_mode_ext.xml',
        'views/oacis_academic_cleanup.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
