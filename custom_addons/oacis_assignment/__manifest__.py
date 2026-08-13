{
    'name': 'Oacis Assignments',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Course assignments, submissions, rubrics and grading for Oacis ERP',
    'description': """
        Course assignments, submissions, rubrics and grading for Oacis ERP.

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
        'oacis_curriculum',
        'oacis_admission',
        'oacis_faculty_profile',
        'oacis_student',
        'oacis_timetable',
        'oacis_notify',
    ],
    'data': [
        'security/oacis_assignment_record_rules.xml',
        'security/ir.model.access.csv',
        'data/oacis_assignment_sequence_data.xml',
        'data/oacis_assignment_notify_data.xml',
        'views/oacis_assignment_rubric_views.xml',
        'views/oacis_assignment_views.xml',
        'views/oacis_assignment_submission_views.xml',
        'views/oacis_assignment_kanban_views.xml',
        'views/oacis_assignment_calendar_views.xml',
        'views/oacis_assignment_analysis_views.xml',
        'views/oacis_course_offering_ext_views.xml',
        'views/oacis_student_ext_views.xml',
        'menus/oacis_assignment_menus.xml',
        'views/oacis_assignment_view_mode_ext.xml',
        'views/oacis_assignment_cleanup.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'oacis_assignment,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
