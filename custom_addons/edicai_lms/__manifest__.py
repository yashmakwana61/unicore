{
    'name': "Edicai LMS",

    'summary': "Advanced Learning Management System for Edicai",

    'description': """
Advanced LMS integrating Odoo eLearning with Edicai Academic structure.
Supports both public B2C courses (free/paid) and internal university academic courses.
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Edicai/LMS',
    'version': '1.0',

    'depends': [
        'base',
        'website_slides',
        'website_sale_slides',
        'edicai_academic',
        'edicai_student',
        'edicai_assignment',
        'edicai_quiz',
        'edicai_gradebook',
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
