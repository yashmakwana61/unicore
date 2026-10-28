{
    'name': 'Edicai Student Portal',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student self-service portal for '
               'academic records, fees and results',
    'description': """
        Edicai Student Portal provides web-based
        self-service access for students:

        - Dashboard: overview of current semester
          enrollment, CGPA, attendance summary
          and fee status
        - My Courses: enrolled courses with timetable
        - My Attendance: per-course attendance records
          with shortage alerts
        - My Exam: hall tickets and exam schedule
        - My Results: published grade entries and
          semester results
        - My Fees: fee invoices and payment history
        - My Scholarships: application status and
          award records

        Students access via /my/edicai/student/
        after logging in as portal users.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'edicai_base', 'edicai_security',
        'edicai_campus', 'edicai_academic',
        'edicai_calendar', 'edicai_student',
        'edicai_faculty_profile', 'edicai_guardian',
        'edicai_curriculum', 'edicai_timetable',
        'edicai_admission', 'edicai_attendance',
        'edicai_exam', 'edicai_grading',
        'edicai_fees', 'edicai_scholarship',
        'edicai_notify', 'edicai_assignment',
        'edicai_notice_board',
        'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_student_templates.xml',
        'views/portal_student_assignment_templates.xml',
        'views/edicai_student_ext_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'edicai_portal_student/static/src/css/'
            'edicai_portal.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
