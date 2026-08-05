{
    'name': 'UniCore Grade Book',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Per-course assignment grade book with CA weighting for UniCore ERP',
    'description': """
        UniCore Grade Book
        ==================

        A running, per-course view of all assignment scores across the
        semester, with weighting configuration (e.g. assignments = 20%
        of the continuous assessment / internal marks).

        The grade book is fully additive:
        - It aggregates the existing unicore.assignment submission data.
        - It feeds the computed assignment component into the existing
          ``internal_marks`` (Internal / CA Marks) field of the
          ``unicore.grade.entry`` model — no schema change.
        - It never bypasses the unicore_grading business rules: grade
          entry state transitions stay owned by that module and CA
          marks are only pushed to entries in an editable state
          (draft / submitted), bounded by the grading constraints.

        Features
        --------
        - One grade book config per course offering
        - Configurable assignment weight (% of CA marks)
        - Per-student roll-up of graded assignment scores
        - Weighted CA component ready to apply to grade entries
        - Smart button on the course offering form
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_assignment',
        'unicore_base',
        'unicore_curriculum',
        'unicore_enrollment',
        'unicore_grading',
    ],
    'data': [
        'security/unicore_gradebook_record_rules.xml',
        'security/ir.model.access.csv',
        'views/unicore_gradebook_views.xml',
        'views/unicore_gradebook_student_line_views.xml',
        'views/unicore_gradebook_assignment_line_views.xml',
        'views/unicore_course_offering_ext_views.xml',
        'menus/unicore_gradebook_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
