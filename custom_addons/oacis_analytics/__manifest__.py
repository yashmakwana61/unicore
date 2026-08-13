{
    'name': 'Analytics',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Institutional analytics dashboards '
               'for academic, financial and student data',
    'description': """
        Oacis Analytics provides a comprehensive
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
        'oacis_base', 'oacis_security',
        'oacis_campus', 'oacis_academic',
        'oacis_calendar', 'oacis_student',
        'oacis_faculty_profile', 'oacis_guardian',
        'oacis_curriculum', 'oacis_timetable',
        'oacis_attendance',
        'oacis_exam', 'oacis_grading',
        'oacis_fees', 'oacis_scholarship',
        'oacis_admission', 'oacis_library',
        'oacis_hostel', 'oacis_transport',
        'mail',
    ],
    'data': [
        'security/oacis_analytics_record_rules.xml',
        'security/ir.model.access.csv',
        'data/oacis_analytics_cron.xml',
        'views/oacis_student_analytics_views.xml',
        'views/oacis_academic_analytics_views.xml',
        'views/oacis_financial_analytics_views.xml',
        'views/oacis_admission_analytics_views.xml',
        'menus/oacis_analytics_menus.xml',
        'views/admission_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'oacis_analytics/static/src/scss/admission_dashboard.scss',
            'oacis_analytics/static/src/xml/admission_dashboard.xml',
            'oacis_analytics/static/src/js/admission_dashboard.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'web_icon': 'oacis_analytics,'
                'static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
