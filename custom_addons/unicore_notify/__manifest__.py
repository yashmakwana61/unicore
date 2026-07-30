{
    'name': 'Notifications',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Multi-channel notification engine '
               'for email, WhatsApp and in-app alerts',
    'description': """
        UniCore Notifications provides a unified
        notification engine for UniCore ERP:

        - Notification Templates: reusable message
          templates with Jinja2-style variable
          substitution for email and WhatsApp
        - WhatsApp Business API Integration:
          HTTP-based message delivery via Meta
          WhatsApp Business Cloud API
        - Email Delivery: via Odoo native mail.mail
        - Notification Log: complete audit trail
          of all sent/failed notifications
        - Company-Level Config: API credentials and
          default settings per institution

        Other modules call this engine's methods
        to send notifications on events such as
        fee due, attendance shortage, exam reminder,
        result published, etc.
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
        'mail',
    ],
    'data': [
        'security/unicore_notify_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_notify_config_data.xml',
        'data/unicore_notify_template_data.xml',
        'views/unicore_notification_config_views.xml',
        'views/unicore_notification_template_views.xml',
        'views/unicore_notification_log_views.xml',
        'menus/unicore_notify_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_notify,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
