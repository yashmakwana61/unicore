{
    'name': 'Scholarships',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Scholarship programs, applications '
               'and financial aid disbursement',
    'description': """
        UniCore Scholarships is a standalone
        application for managing student financial aid:

        - Scholarship Programs: define merit, need-based,
          sports and government scholarship schemes with
          configurable eligibility criteria
        - Applications: students apply and eligibility
          is auto-checked against CGPA, attendance
          and income criteria
        - Awards: disbursement records per semester
          with optional direct fee invoice adjustment
        - Dashboard: track scholarship spend, coverage
          and beneficiary counts per program

        Appears as a dedicated app in the Odoo
        home screen.
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
        'unicore_enrollment', 'unicore_attendance',
        'unicore_exam', 'unicore_grading',
        'unicore_fees', 'mail',
    ],
    'data': [
        'security/unicore_scholarship_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_scholarship_sequence_data.xml',
        'views/unicore_scholarship_award_views.xml',
        'views/unicore_scholarship_application_views.xml',
        'views/unicore_scholarship_program_views.xml',
        'views/scholarship_search_list_phase1.xml',
        'views/unicore_student_scholarship_ext_views.xml',
        'menus/unicore_scholarship_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_scholarship,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
