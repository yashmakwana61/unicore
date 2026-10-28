{
    'name': 'Edicai Demo Data',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Realistic demo data for Edicai ERP '
               '— institution-aware datasets',
    'description': """
        Injects demo data into a fresh Edicai installation.

        Two complementary mechanisms:

        - Legacy static dataset: PreciseFect University company setup
          (campus, faculties/departments/programs, semesters, courses,
          faculty, students, guardians, timetable, enrollments, attendance,
          exams, grades, fees, scholarships, admissions, documents, hostel,
          library, transport, notifications). Preserved for backward
          compatibility.
        - Institution-aware generator: Edicai / Configuration / Demo Data /
          Generate Demo Data. Detects the institution type from the
          company's institution profile and builds only the matching
          dataset (University, College, K-12 School, Training Institute,
          Academy / Test-Prep, Coaching Center). Company-scoped, tracked
          per record, and safely resettable without touching real data.

        Covers ALL edicai custom addon modules.
        Uses search-or-create patterns.
        Re-runnable via module upgrade.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'edicai_institution_profile',
        'edicai_base',
        'edicai_security',
        'edicai_campus',
        'edicai_academic',
        'edicai_calendar',
        'edicai_student',
        'edicai_faculty_profile',
        'edicai_guardian',
        'edicai_curriculum',
        'edicai_timetable',
        'edicai_attendance',
        'edicai_exam',
        'edicai_grading',
        'edicai_fees',
        'edicai_scholarship',
        'edicai_admission',
        'edicai_documents',
        'edicai_hostel',
        'edicai_library',
        'edicai_transport',
        'edicai_notify',
        'edicai_assignment',
        'edicai_api',
        'edicai_analytics',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/demo_profiles.xml',
        'views/demo_views.xml',
        'demo/00_company_setup.xml',
        'demo/00_accounting_setup.xml',
        'demo/01_campus_data.xml',
        'demo/02_academic_structure.xml',
        'demo/03_academic_calendar.xml',
        'demo/04_curriculum_data.xml',
        'demo/05_faculty_data.xml',
        'demo/06_student_data.xml',
        'demo/07_guardian_data.xml',
        'demo/08_timetable_data.xml',
        'demo/09_enrollment_data.xml',
        'demo/10_attendance_data.xml',
        'demo/11_exam_data.xml',
        'demo/12_grading_data.xml',
        'demo/13_fees_data.xml',
        'demo/14_scholarship_data.xml',
        'demo/15_admission_data.xml',
        'demo/16_document_data.xml',
        'demo/17_hostel_data.xml',
        'demo/18_library_data.xml',
        'demo/19_transport_data.xml',
        'demo/20_notification_data.xml',
        'demo/21_assignment_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
