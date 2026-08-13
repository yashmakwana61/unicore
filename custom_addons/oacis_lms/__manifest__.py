{
    'name': "Oacis LMS",

    'summary': "Advanced Learning Management System for Oacis",

    'description': """
Advanced LMS integrating Odoo eLearning with Oacis Academic structure.
Supports both public B2C courses (free/paid) and internal university academic courses.
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Oacis/LMS',
    'version': '1.0',

    'depends': [
        'base',
        'website_slides',
        'website_sale_slides',
        'oacis_academic',
        'oacis_student',
        'oacis_assignment',
        'oacis_quiz',
        'oacis_gradebook',
    ],

    'data': [
        'views/menu_views.xml',
        'views/slide_channel_views.xml',
        'views/slide_slide_views.xml',
        'views/slide_channel_gradebook_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    'license': 'OPL-1',

    'auto_install': False,
}
