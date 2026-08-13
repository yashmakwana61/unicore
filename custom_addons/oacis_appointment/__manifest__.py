{
    'name': 'Oacis Appointment',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Online Appointment Booking',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['oacis_student', 'oacis_faculty_profile'],
    'data': [
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'views/appointment_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
