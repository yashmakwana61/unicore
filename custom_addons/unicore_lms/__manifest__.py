# -*- coding: utf-8 -*-
{
    'name': "Unicore LMS",

    'summary': "Advanced Learning Management System for Unicore",

    'description': """
Advanced LMS integrating Odoo eLearning with Unicore Academic structure.
Supports both public B2C courses (free/paid) and internal university academic courses.
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Unicore/LMS',
    'version': '1.0',

    'depends': [
        'base', 
        'website_slides', 
        'website_sale_slides', 
        'unicore_academic', 
        'unicore_student',
        'unicore_assignment',
        'unicore_quiz',
        'unicore_gradebook'
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
    'license': 'LGPL-3',
}
