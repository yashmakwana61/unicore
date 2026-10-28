{
    'name': 'Edicai Guardian Portal',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Guardian self-service portal for ward '
               'academic and fee monitoring',
    'description': """
        Edicai Guardian Portal provides web-based
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

        Guardian access via /my/edicai/guardian/
        All data access gated by permission flags
        set on the guardian-student relationship.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'edicai_base', 'edicai_security',
        'edicai_campus', 'edicai_academic',
        'edicai_calendar', 'edicai_student',
        'edicai_guardian', 'edicai_curriculum',
        'edicai_admission', 'edicai_attendance',
        'edicai_exam', 'edicai_grading',
        'edicai_fees', 'edicai_notify',
        'edicai_portal_student', 'edicai_notice_board',
        'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_guardian_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
