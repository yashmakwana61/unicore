{
    'name': 'Fees',
    'version': '19.0.1.1.0',
    'category': 'Education',
    'summary': 'Student fee management, invoicing and payment tracking',
    'description': """
UniCore Fees is a standalone application for managing student fee operations:

- Fee Structures: configurable per program, semester and campus with line-item breakdown
- Fee Invoices: auto-generated per student per semester with installment support
- Fee Payments: payment recording and outstanding balance tracking
- Financial Dashboard: revenue, outstanding and collection rate reporting

Appears as a dedicated app in the Odoo home screen alongside other Odoo apps.
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
        'unicore_exam', 'unicore_grading', 'mail',
        'account',
    ],
    'data': [
        'security/unicore_fees_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_fees_sequence_data.xml',
        'data/unicore_fees_cron_data.xml',
        'views/unicore_student_partner_ext_views.xml',
        'views/unicore_fee_structure_views.xml',
        'views/unicore_fee_invoice_views.xml',
        'views/unicore_fee_invoice_gl_ext_views.xml',
        'views/unicore_student_fee_ext_views.xml',
        'views/unicore_fee_receipt_template.xml',
        'data/unicore_fee_receipt_report_action.xml',
        'views/unicore_fee_accounting_config_views.xml',
        'views/unicore_fee_batch_wizard_views.xml',
        'views/fee_invoice_search_phase1.xml',
        'menus/unicore_fees_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'web_icon': 'unicore_fees,static/description/icon.png',
    'post_init_hook': 'post_init_hook',
}
