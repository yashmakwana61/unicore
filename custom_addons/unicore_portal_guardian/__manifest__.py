{
    'name': 'UniCore Guardian Portal',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Guardian self-service portal for ward '
               'academic and fee monitoring',
    'description': """
        UniCore Guardian Portal provides web-based
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

        Guardian access via /my/unicore/guardian/
        All data access gated by permission flags
        set on the guardian-student relationship.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base', 'unicore_security',
        'unicore_campus', 'unicore_academic',
        'unicore_calendar', 'unicore_student',
        'unicore_guardian', 'unicore_curriculum',
        'unicore_enrollment', 'unicore_attendance',
        'unicore_exam', 'unicore_grading',
        'unicore_fees', 'unicore_notify',
        'unicore_portal_student', 'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_guardian_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
