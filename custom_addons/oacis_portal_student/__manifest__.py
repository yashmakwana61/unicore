{
    'name': 'UniCore Student Portal',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student self-service portal for '
               'academic records, fees and results',
    'description': """
        UniCore Student Portal provides web-based
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

        Students access via /my/unicore/student/
        after logging in as portal users.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base', 'unicore_security',
        'unicore_campus', 'unicore_academic',
        'unicore_calendar', 'unicore_student',
        'unicore_faculty_profile', 'unicore_guardian',
        'unicore_curriculum', 'unicore_timetable',
        'unicore_admission', 'unicore_attendance',
        'unicore_exam', 'unicore_grading',
        'unicore_fees', 'unicore_scholarship',
        'unicore_notify', 'unicore_assignment',
        'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_student_templates.xml',
        'views/portal_student_assignment_templates.xml',
        'views/unicore_student_ext_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'unicore_portal_student/static/src/css/'
            'unicore_portal.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
