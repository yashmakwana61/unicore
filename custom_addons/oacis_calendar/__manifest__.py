{
    'name': 'Oacis Academic Calendar',
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
        'oacis_academic',
        'oacis_base',
        'oacis_campus',
        'oacis_security',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/oacis_generate_weeks_wizard_views.xml',
        'views/oacis_academic_year_views.xml',
        'views/oacis_semester_views.xml',
        'views/oacis_academic_week_views.xml',
        'views/oacis_holiday_views.xml',
        'views/oacis_calendar_kanban_views.xml',
        'views/oacis_calendar_calendar_views.xml',
        'menus/oacis_calendar_menus.xml',
        'views/oacis_calendar_view_mode_ext.xml',
        'views/oacis_calendar_cleanup.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
