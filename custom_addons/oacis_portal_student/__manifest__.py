{
    'name': 'Oacis Student Portal',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student self-service portal for '
               'academic records, fees and results',
    'description': """
        Oacis Student Portal provides web-based
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

        Students access via /my/oacis/student/
        after logging in as portal users.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'oacis_base', 'oacis_security',
        'oacis_campus', 'oacis_academic',
        'oacis_calendar', 'oacis_student',
        'oacis_faculty_profile', 'oacis_guardian',
        'oacis_curriculum', 'oacis_timetable',
        'oacis_admission', 'oacis_attendance',
        'oacis_exam', 'oacis_grading',
        'oacis_fees', 'oacis_scholarship',
        'oacis_notify', 'oacis_assignment',
        'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_student_templates.xml',
        'views/portal_student_assignment_templates.xml',
        'views/oacis_student_ext_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'oacis_portal_student/static/src/css/'
            'oacis_portal.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
