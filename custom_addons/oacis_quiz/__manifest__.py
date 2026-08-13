{
    'name': 'UniCore Quiz',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Quiz / Question Bank + Anti-Cheating',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['unicore_student', 'unicore_theme'],
    'data': [
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'views/quiz_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'unicore_quiz/static/src/js/quiz_action.js',
            'unicore_quiz/static/src/xml/quiz_action.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
