{
    'name': 'Oacis Faculty Portal',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Faculty self-service portal for '
               'schedule, attendance and grade entry',
    'description': """
        Oacis Faculty Portal provides web-based
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

        Faculty access via /my/oacis/faculty/
        Works for both internal and portal users.
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
        'oacis_portal_student',
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
