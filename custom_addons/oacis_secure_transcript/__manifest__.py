{
    'name': 'Oacis Secure Transcript',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Secure Transcript with QR Verification',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['oacis_student', 'oacis_grading', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/transcript_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
