{
    'name': 'UniCore Academic Calendar',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Academic year, semester, term and holiday management',
    'description': '''
Manages the complete academic time structure for UniCore ERP.
Defines Academic Years, Semesters, Academic Weeks,
Holidays and institutional Events.
All academic operations depend on this calendar.
    ''',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'LGPL-3',
    'depends': [
        'unicore_base',
        'unicore_security',
        'unicore_campus',
        'unicore_academic',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/unicore_generate_weeks_wizard_views.xml',
        'views/unicore_academic_year_views.xml',
        'views/unicore_semester_views.xml',
        'views/unicore_academic_week_views.xml',
        'views/unicore_holiday_views.xml',
        'menus/unicore_calendar_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
