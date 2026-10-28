{
    'name': 'Edicai Grade Book',
    'version': '19.0.1.1.0',
    'category': 'Education',
    'summary': 'Per-course assignment grade book with CA weighting, integrated with Grading & Results',
    'description': """
        Edicai Grade Book
        ==================

        A running, per-course view of all assignment scores across the
        semester, with weighting configuration (e.g. assignments = 20%
        of the continuous assessment / internal marks). Deeply
        integrated with the ``edicai_grading`` module: the grade book
        rolls up graded assignment submissions and proposes the
        weighted CA component for the existing
        ``edicai.grade.entry.internal_marks`` field.

        Architecture note
        -----------------
        The grade book models reference ``edicai.assignment`` records
        (score snapshots per assignment). ``edicai_assignment`` sits
        above ``edicai_grading`` in the module dependency graph
        (``assignment -> notify -> fees -> grading``), so these models
        cannot physically live inside ``edicai_grading`` without a
        dependency cycle. This module therefore remains the host for
        the grade book, while all of it is fully integrated with the
        grading module's data (grade entries, state machine, reports).

        Enhancements (19.0.1.1.0)
        -------------------------
        - Auto-refresh: graded submission create / edit / delete
          re-rolls the affected grade books automatically (no manual
          "Regenerate Grade Book" needed for day-to-day grading).
        - Batch roll-up: one ``Submission`` search per offering instead
          of one per enrollment (N+1 fixed).
        - Grade entry linkage fixed: lines pick up grade entries
          created after them, and ``is_synced`` uses a rounding
          tolerance.
        - UX: config form summary with sync progress bar, stat buttons
          (Students / Graded Assignments), per-line "Apply this line"
          and "Open Grade Entry" actions.
        - Reports: Grade Book / Mark Sheet PDF per offering.
        - Security model and business rules unchanged: CA marks are
          only pushed to draft / submitted grade entries within
          ``[0, internal_max]`` and ``entry_state`` is never written.

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
        'edicai_assignment',
        'edicai_grading',
    ],
    'data': [
        'security/edicai_gradebook_record_rules.xml',
        'security/ir.model.access.csv',
        'data/edicai_gradebook_report_action.xml',
        'views/edicai_gradebook_views.xml',
        'views/edicai_gradebook_student_line_views.xml',
        'views/edicai_gradebook_assignment_line_views.xml',
        'views/edicai_course_offering_ext_views.xml',
        'views/edicai_gradebook_template.xml',
        'menus/edicai_gradebook_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
