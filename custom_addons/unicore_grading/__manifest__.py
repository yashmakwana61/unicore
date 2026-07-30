{
    'name': 'Grading & Results',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Marks entry, grade computation, '
               'GPA/CGPA and semester results',
    'description': """
        Manages the complete grading lifecycle
        for UniCore ERP:

        - Grade Scale: configurable letter grade
          and grade point mapping per institution
        - Grade Entry: marks entry per student per
          course with auto grade computation
        - Semester Result: per-student semester
          summary with GPA and pass/fail determination
        - Transcript data: feeds student CGPA and
          credit accumulation

        Closes the academic operations loop:
        enrollment → attendance → exam → grading
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
        'unicore_exam',
    ],
    'data': [
        'security/unicore_grading_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_grade_scale_data.xml',
        'data/unicore_transcript_report_action.xml',
        'views/unicore_grade_scale_views.xml',
        'views/unicore_grade_entry_views.xml',
        'views/unicore_semester_result_views.xml',
        'views/grading_search_list_phase1.xml',
        'views/unicore_student_result_views.xml',
        'views/unicore_transcript_template.xml',
        'menus/unicore_grading_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_grading,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
