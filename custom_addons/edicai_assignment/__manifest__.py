{
    'name': 'Edicai Assignments',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Course assignments, submissions, rubrics and grading for Edicai ERP',
    'description': """
        Course assignments, submissions, rubrics and grading for Edicai ERP.

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
        'edicai_curriculum',
        'edicai_admission',
        'edicai_faculty_profile',
        'edicai_student',
        'edicai_timetable',
        'edicai_notify',
    ],
    'data': [
        'security/edicai_assignment_record_rules.xml',
        'security/ir.model.access.csv',
        'data/edicai_assignment_sequence_data.xml',
        'data/edicai_assignment_notify_data.xml',
        'views/edicai_assignment_rubric_views.xml',
        'views/edicai_assignment_views.xml',
        'views/edicai_assignment_submission_views.xml',
        'views/edicai_assignment_kanban_views.xml',
        'views/edicai_assignment_calendar_views.xml',
        'views/edicai_assignment_analysis_views.xml',
        'views/edicai_course_offering_ext_views.xml',
        'views/edicai_student_ext_views.xml',
        'menus/edicai_assignment_menus.xml',
        'views/edicai_assignment_view_mode_ext.xml',
        'views/edicai_assignment_cleanup.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'edicai_assignment,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
