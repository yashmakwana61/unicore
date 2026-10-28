{
    'name': 'Edicai Faculty Portal',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Faculty self-service portal for '
               'schedule, attendance and grade entry',
    'description': """
        Edicai Faculty Portal provides web-based
        self-service access for faculty members:

        - Dashboard: today's classes, pending grade
          entries, upcoming exams as invigilator
        - My Schedule: weekly timetable view with
          room and course details
        - My Courses: enrolled student list per
          course with attendance summary
        - Attendance Entry: mark/update attendance
          for open sessions directly from portal
        - Grade Entry: enter and submit internal
          marks for students in own courses
        - My Exams: exam schedules where assigned
          as invigilator or chief invigilator
        - My Profile: qualifications, workload
          summary and contact details

        Faculty access via /my/edicai/faculty/
        Works for both internal and portal users.
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
        'edicai_portal_student',
        'edicai_notice_board',
        'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_faculty_templates.xml',
        'views/portal_faculty_assignment_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
