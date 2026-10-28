{
    'name': 'Edicai Guardians',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Parent and guardian profile management '
               'with portal access',
    'description': """
        Manages guardian and parent profiles as
        first-class records in Edicai ERP.

        Guardians can be linked to multiple students.
        Supports financial guarantor designation,
        communication history and portal access for
        monitoring academic progress and fee status.

        DESIGN: edicai.guardian owns the relationship
        to edicai.student via edicai.guardian.student.rel.
        Guardians are NOT owned by students.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'edicai_base',
        'edicai_security',
        'edicai_campus',
        'edicai_academic',
        'edicai_calendar',
        'edicai_student',
        'edicai_faculty_profile',
    ],
    'data': [
        'security/edicai_guardian_record_rules.xml',
        'security/ir.model.access.csv',
        'data/edicai_guardian_sequence_data.xml',
        'views/edicai_guardian_views.xml',
        'views/edicai_guardian_student_rel_views.xml',
        'views/edicai_student_ext_views.xml',
        'menus/edicai_guardian_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
