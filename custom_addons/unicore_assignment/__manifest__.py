{
    'name': 'UniCore Assignments',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Course assignments, submissions, rubrics and grading for UniCore ERP',
    'description': """
        Course assignments, submissions, rubrics and grading for UniCore ERP.

        Faculty create assignments per course offering with optional
        rubric-based grading. Students submit work (file upload) through
        the student portal. Faculty grade submissions with rubrics and
        can annotate submitted files with positional comments.

        - Assignment management (homework / project / lab / quiz)
        - Reusable rubrics with criteria and max points
        - Student file submissions with late detection
        - Rubric-based grading with feedback and annotations
        - Portal touchpoints in student and faculty portals
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_curriculum',
        'unicore_enrollment',
        'unicore_faculty_profile',
        'unicore_student',
        'unicore_timetable',
        'unicore_notify',
    ],
    'data': [
        'security/unicore_assignment_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_assignment_sequence_data.xml',
        'data/unicore_assignment_notify_data.xml',
        'views/unicore_assignment_rubric_views.xml',
        'views/unicore_assignment_views.xml',
        'views/unicore_assignment_submission_views.xml',
        'views/unicore_assignment_kanban_views.xml',
        'views/unicore_assignment_calendar_views.xml',
        'views/unicore_assignment_analysis_views.xml',
        'views/unicore_course_offering_ext_views.xml',
        'views/unicore_student_ext_views.xml',
        'menus/unicore_assignment_menus.xml',
        'views/unicore_assignment_view_mode_ext.xml',
        'views/unicore_assignment_cleanup.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
