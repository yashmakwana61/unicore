{
    'name': 'Analytics',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Institutional analytics dashboards '
               'for academic, financial and student data',
    'description': """
        UniCore Analytics provides a comprehensive
        analytics suite for university administration:

        - Student Analytics: enrollment trends,
          gender distribution, program-wise counts,
          CGPA distribution, dropout rates
        - Academic Analytics: course-wise pass/fail
          rates, attendance trends, grade distributions,
          faculty workload analysis
        - Financial Analytics: fee collection rates,
          outstanding fees, payment method trends,
          scholarship impact on revenue
        - Admission Analytics: application funnel,
          conversion rates, category-wise analysis,
          entrance score distribution

        All reports use PostgreSQL VIEWs for
        high-performance read-only analytics.
        No transactional data is modified.
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
        'unicore_fees', 'unicore_scholarship',
        'unicore_admission', 'unicore_library',
        'unicore_hostel', 'unicore_transport',
        'mail',
    ],
    'data': [
        'security/unicore_analytics_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_analytics_cron.xml',
        'views/unicore_student_analytics_views.xml',
        'views/unicore_academic_analytics_views.xml',
        'views/unicore_financial_analytics_views.xml',
        'views/unicore_admission_analytics_views.xml',
        'menus/unicore_analytics_menus.xml',
        'views/admission_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'unicore_analytics/static/src/scss/admission_dashboard.scss',
            'unicore_analytics/static/src/xml/admission_dashboard.xml',
            'unicore_analytics/static/src/js/admission_dashboard.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_analytics,'
                'static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
