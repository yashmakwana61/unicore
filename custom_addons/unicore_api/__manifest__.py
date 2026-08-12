{
    'name': 'UniCore API',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'RESTful API gateway for UniCore ERP',
    'description': """
UniCore API
===========

RESTful API gateway for the UniCore University Management System.

Provides a secure, authenticated REST API for external integrations
including mobile apps, portals, and third-party systems.

Key features:
- Custom X-UniCore-Key authentication header
- Scope-based access control (read, write, admin)
- Daily rate limiting per API key
- Usage tracking and expiry management
- RESTful JSON endpoints for core domain models
- Student information, enrollment, attendance, grades, fees
- Academic structure (programs, semesters, courses)
- Notification dispatch
- Health check and system information endpoints
- Swagger/OpenAPI compatible response format

All endpoints return consistent JSON structure:
  {success: true/false, data: {...}, meta: {...}}
  {success: false, error: 'message', code: 'ERROR_CODE'}
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base',
        'unicore_security',
        'unicore_student',
        'unicore_academic',
        'unicore_admission',
        'unicore_attendance',
        'unicore_grading',
        'unicore_fees',
        'unicore_notify',
        'unicore_curriculum',
    ],
    'data': [
        'security/groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/api_key_views.xml',
        'menus/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'web_icon': 'unicore_api,'
                'static/description/icon.png',
}
