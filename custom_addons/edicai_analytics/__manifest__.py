{
    'name': 'Analytics',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Institutional analytics dashboards '
               'for academic, financial and student data',
    'description': """
        Edicai Analytics provides a comprehensive
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
        'edicai_base', 'edicai_security',
        'edicai_campus', 'edicai_academic',
        'edicai_calendar', 'edicai_student',
        'edicai_faculty_profile', 'edicai_guardian',
        'edicai_curriculum', 'edicai_timetable',
        'edicai_attendance',
        'edicai_exam', 'edicai_grading',
        'edicai_fees', 'edicai_scholarship',
        'edicai_admission', 'edicai_library',
        'edicai_hostel', 'edicai_transport',
        'mail',
    ],
    'data': [
        'security/edicai_analytics_record_rules.xml',
        'security/ir.model.access.csv',
        'data/edicai_analytics_cron.xml',
        'views/edicai_student_analytics_views.xml',
        'views/edicai_academic_analytics_views.xml',
        'views/edicai_financial_analytics_views.xml',
        'views/edicai_admission_analytics_views.xml',
        'menus/edicai_analytics_menus.xml',
        'views/admission_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edicai_analytics/static/src/scss/admission_dashboard.scss',
            'edicai_analytics/static/src/xml/admission_dashboard.xml',
            'edicai_analytics/static/src/js/admission_dashboard.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'web_icon': 'edicai_analytics,'
                'static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
