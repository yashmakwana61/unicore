{
    'name': 'UniCore Demo Data',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Realistic demo data for UniCore ERP '
               '— PreciseFect University',
    'description': """
        Injects complete demo data into a fresh
        UniCore installation.

        Includes:
        - PreciseFect University company setup
        - 1 campus with buildings and rooms
        - 2 faculties, 3 departments, 3 programs
        - Academic year 2025-26 with 2 semesters
        - 8 demo courses with prerequisites
        - 2 faculty members + 1 admin staff
        - 10 demo students across 3 programs
        - 10 guardians (parents) linked to students
        - Timetable entries for current semester
        - Course enrollments for all students
        - Attendance records for 4 sessions
        - Exam schedule with hall tickets
        - Grade entries for completed courses
        - Fee structures, invoices and payments
        - 2 scholarship programs with applications
        - Admission cycle with applicants
        - Document categories and templates
        - Hostel blocks, rooms and allocations
        - Library books, copies and members
        - Transport vehicles, routes and passes
        - Notification templates

        Covers ALL unicore custom addon modules.
        Uses search-or-create patterns.
        Re-runnable via module upgrade.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base',
        'unicore_security',
        'unicore_campus',
        'unicore_academic',
        'unicore_calendar',
        'unicore_student',
        'unicore_faculty_profile',
        'unicore_guardian',
        'unicore_curriculum',
        'unicore_timetable',
        'unicore_attendance',
        'unicore_exam',
        'unicore_grading',
        'unicore_fees',
        'unicore_scholarship',
        'unicore_admission',
        'unicore_documents',
        'unicore_hostel',
        'unicore_library',
        'unicore_transport',
        'unicore_notify',
        'unicore_assignment',
        'unicore_api',
        'unicore_analytics',
    ],
    'data': [
        'data/00_company_setup.xml',
        'data/01_campus_data.xml',
        'data/02_academic_structure.xml',
        'data/03_academic_calendar.xml',
        'data/04_curriculum_data.xml',
        'data/05_faculty_data.xml',
        'data/06_student_data.xml',
        'data/07_guardian_data.xml',
        'data/08_timetable_data.xml',
        'data/09_enrollment_data.xml',
        'data/10_attendance_data.xml',
        'data/11_exam_data.xml',
        'data/12_grading_data.xml',
        'data/13_fees_data.xml',
        'data/14_scholarship_data.xml',
        'data/15_admission_data.xml',
        'data/16_document_data.xml',
        'data/17_hostel_data.xml',
        'data/18_library_data.xml',
        'data/19_transport_data.xml',
        'data/20_notification_data.xml',
        'data/21_assignment_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
