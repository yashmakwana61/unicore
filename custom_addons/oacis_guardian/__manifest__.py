{
    'name': 'Oacis Guardians',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Parent and guardian profile management '
               'with portal access',
    'description': """
        Manages guardian and parent profiles as
        first-class records in Oacis ERP.

        Guardians can be linked to multiple students.
        Supports financial guarantor designation,
        communication history and portal access for
        monitoring academic progress and fee status.

        DESIGN: oacis.guardian owns the relationship
        to oacis.student via oacis.guardian.student.rel.
        Guardians are NOT owned by students.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'oacis_base',
        'oacis_security',
        'oacis_campus',
        'oacis_academic',
        'oacis_calendar',
        'oacis_student',
        'oacis_faculty_profile',
    ],
    'data': [
        'security/oacis_guardian_record_rules.xml',
        'security/ir.model.access.csv',
        'data/oacis_guardian_sequence_data.xml',
        'views/oacis_guardian_views.xml',
        'views/oacis_guardian_student_rel_views.xml',
        'views/oacis_student_ext_views.xml',
        'menus/oacis_guardian_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
