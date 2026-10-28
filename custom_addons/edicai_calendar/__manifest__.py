{
    'name': 'Edicai Academic Calendar',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Academic year, semester, term and holiday management',
    'description': """
        Academic year, semester, term and holiday management
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'edicai_academic',
        'edicai_base',
        'edicai_campus',
        'edicai_security',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/edicai_generate_weeks_wizard_views.xml',
        'views/edicai_academic_year_views.xml',
        'views/edicai_semester_views.xml',
        'views/edicai_academic_week_views.xml',
        'views/edicai_holiday_views.xml',
        'views/edicai_calendar_kanban_views.xml',
        'views/edicai_calendar_calendar_views.xml',
        'menus/edicai_calendar_menus.xml',
        'views/edicai_calendar_view_mode_ext.xml',
        'views/edicai_calendar_cleanup.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
