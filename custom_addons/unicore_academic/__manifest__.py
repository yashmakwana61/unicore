{
    'name': 'UniCore Academic Structure',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Faculty, Department, Program and Specialisation management',
    'description': '''
Defines the complete academic hierarchy for UniCore ERP.
Manages Faculties, Departments, Programs and Specialisations
across multiple campuses and institutions.
    ''',
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base',
        'unicore_security',
        'unicore_campus',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/unicore_program_type_data.xml',
        'views/unicore_faculty_views.xml',
        'views/unicore_department_views.xml',
        'views/unicore_program_views.xml',
        'views/unicore_specialisation_views.xml',
        'menus/unicore_academic_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
