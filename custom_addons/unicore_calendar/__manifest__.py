{
    'name': 'UniCore Academic Calendar',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Academic year, semester, term and holiday management',
    'description': """
        Academic year, semester, term and holiday management
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'LGPL-3',
    'depends': [
        'unicore_academic',
        'unicore_base',
        'unicore_campus',
        'unicore_security',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/unicore_generate_weeks_wizard_views.xml',
        'views/unicore_academic_year_views.xml',
        'views/unicore_semester_views.xml',
        'views/unicore_academic_week_views.xml',
        'views/unicore_holiday_views.xml',
        'views/unicore_calendar_kanban_views.xml',
        'views/unicore_calendar_calendar_views.xml',
        'menus/unicore_calendar_menus.xml',
        'views/unicore_calendar_view_mode_ext.xml',
        'views/unicore_calendar_cleanup.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
