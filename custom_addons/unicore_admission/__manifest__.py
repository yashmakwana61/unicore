{
    'name': 'Admission Management',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Complete admission lifecycle from inquiry to confirmed enrollment',
    'description': """
        Manages the full admission workflow in UniCore ERP.
        Supports 13-state progression: Inquiry → Applied → Documents Pending
        → Under Review → Shortlisted → Entrance Scheduled → Merit Listed
        → Offer Sent → Fee Pending → Confirmed / Rejected / Withdrawn / Waitlisted.

        Features:
        - Admission cycles with configurable seat allocation per program
        - Applicant tracking with document submission status
        - Entrance test scheduling and result management
        - Composite score calculation (aggregate + entrance + interview)
        - Offer letter generation and acceptance tracking
        - Auto-create student record on admission confirmation
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
        'unicore_fees',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/unicore_admission_record_rules.xml',
        'data/admission_sequence_data.xml',
        'views/admission_cycle_views.xml',
        'views/admission_applicant_views.xml',
        'views/entrance_test_views.xml',
        'views/offer_letter_views.xml',
        'views/admission_search_list_phase1.xml',
        'menus/admission_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'unicore_admission/static/src/scss/admission_kanban.scss',
        ],
    },
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_admission,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
