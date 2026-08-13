{
    'name': 'Oacis API',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'RESTful API gateway for Oacis ERP',
    'description': """
Oacis API
===========

RESTful API gateway for the Oacis University Management System.

Provides a secure, authenticated REST API for external integrations
including mobile apps, portals, and third-party systems.

Key features:
- Custom X-Oacis-Key authentication header
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
        'oacis_base',
        'oacis_security',
        'oacis_student',
        'oacis_academic',
        'oacis_admission',
        'oacis_attendance',
        'oacis_grading',
        'oacis_fees',
        'oacis_notify',
        'oacis_curriculum',
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
    'web_icon': 'oacis_api,'
                'static/description/icon.png',
}
