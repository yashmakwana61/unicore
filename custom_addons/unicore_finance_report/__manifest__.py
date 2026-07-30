{
    'name': 'Finance Reports',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Financial dashboards, fee analytics and revenue reporting',
    'description': """
        UniCore Finance Reports is a standalone
        reporting application providing:

        - Fee Collection Dashboard: real-time
          revenue, outstanding and collection rate
        - Payment Analytics: payment method breakdown,
          collection trends by month
        - Scholarship Analytics: aid distribution
          and coverage reports
        - Student Fee Statement PDF report
        - Financial KPI Snapshots: daily snapshots
          of key financial metrics
        - Pivot and graph views for custom analysis

        Read-only: this module never modifies
        fee or scholarship transactional data.
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
        'unicore_fees', 'unicore_scholarship', 'mail',
    ],
    'data': [
        'security/unicore_finance_report_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_finance_report_cron.xml',
        'views/unicore_fee_invoice_report_views.xml',
        'views/unicore_fee_payment_report_views.xml',
        'views/unicore_finance_snapshot_views.xml',
        'views/unicore_finance_kpi_views.xml',
        'views/unicore_finance_dashboard_views.xml',
        'report/unicore_fee_statement_report.xml',
        'report/unicore_fee_statement_template.xml',
        'menus/unicore_finance_report_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_finance_report,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
