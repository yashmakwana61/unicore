{
    'name': 'Oacis Demo Data',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Realistic demo data for Oacis ERP '
               '— institution-aware datasets',
    'description': """
        Injects demo data into a fresh Oacis installation.

        Two complementary mechanisms:

        - Legacy static dataset: PreciseFect University company setup
          (campus, faculties/departments/programs, semesters, courses,
          faculty, students, guardians, timetable, enrollments, attendance,
          exams, grades, fees, scholarships, admissions, documents, hostel,
          library, transport, notifications). Preserved for backward
          compatibility.
        - Institution-aware generator: Oacis / Configuration / Demo Data /
          Generate Demo Data. Detects the institution type from the
          company's institution profile and builds only the matching
          dataset (University, College, K-12 School, Training Institute,
          Academy / Test-Prep, Coaching Center). Company-scoped, tracked
          per record, and safely resettable without touching real data.

        Covers ALL oacis custom addon modules.
        Uses search-or-create patterns.
        Re-runnable via module upgrade.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'oacis_institution_profile',
        'oacis_base',
        'oacis_security',
        'oacis_campus',
        'oacis_academic',
        'oacis_calendar',
        'oacis_student',
        'oacis_faculty_profile',
        'oacis_guardian',
        'oacis_curriculum',
        'oacis_timetable',
        'oacis_attendance',
        'oacis_exam',
        'oacis_grading',
        'oacis_fees',
        'oacis_scholarship',
        'oacis_admission',
        'oacis_documents',
        'oacis_hostel',
        'oacis_library',
        'oacis_transport',
        'oacis_notify',
        'oacis_assignment',
        'oacis_api',
        'oacis_analytics',
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
