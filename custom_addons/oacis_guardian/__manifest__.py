{
    'name': 'UniCore Guardians',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Parent and guardian profile management '
               'with portal access',
    'description': """
        Manages guardian and parent profiles as
        first-class records in UniCore ERP.

        Guardians can be linked to multiple students.
        Supports financial guarantor designation,
        communication history and portal access for
        monitoring academic progress and fee status.

        DESIGN: unicore.guardian owns the relationship
        to unicore.student via unicore.guardian.student.rel.
        Guardians are NOT owned by students.
    """,
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
        'unicore_faculty_profile',
    ],
    'data': [
        'security/unicore_guardian_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_guardian_sequence_data.xml',
        'views/unicore_guardian_views.xml',
        'views/unicore_guardian_student_rel_views.xml',
        'views/unicore_student_ext_views.xml',
        'menus/unicore_guardian_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
