{
    'name': 'Edicai API',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'RESTful API gateway for Edicai ERP',
    'description': """
Edicai API
===========

RESTful API gateway for the Edicai University Management System.

Provides a secure, authenticated REST API for external integrations
including mobile apps, portals, and third-party systems.

Key features:
- Custom X-Edicai-Key authentication header
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
        'edicai_base',
        'edicai_security',
        'edicai_student',
        'edicai_academic',
        'edicai_admission',
        'edicai_attendance',
        'edicai_grading',
        'edicai_fees',
        'edicai_notify',
        'edicai_curriculum',
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
    'web_icon': 'edicai_api,'
                'static/description/icon.png',
}
