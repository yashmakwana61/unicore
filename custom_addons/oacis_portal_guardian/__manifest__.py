{
    'name': 'Oacis Guardian Portal',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Guardian self-service portal for ward '
               'academic and fee monitoring',
    'description': """
        Oacis Guardian Portal provides web-based
        self-service access for guardians:

        - Dashboard: overview of all wards with
          alerts for attendance shortage, fee due,
          and new grade publications
        - Ward Attendance: per-ward attendance
          records with shortage alerts
        - Ward Academic Performance: grade entries
          and semester results
        - Fee Invoices: outstanding and paid fee
          invoices for each ward
        - Exam Schedule: upcoming exam schedules
          and hall ticket status

        Guardian access via /my/oacis/guardian/
        All data access gated by permission flags
        set on the guardian-student relationship.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'oacis_base', 'oacis_security',
        'oacis_campus', 'oacis_academic',
        'oacis_calendar', 'oacis_student',
        'oacis_guardian', 'oacis_curriculum',
        'oacis_admission', 'oacis_attendance',
        'oacis_exam', 'oacis_grading',
        'oacis_fees', 'oacis_notify',
        'oacis_portal_student', 'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_guardian_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
