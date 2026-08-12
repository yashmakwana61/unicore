{
    'name': 'UniCore Campus Management',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Complete campus, building, room and facility management',
    'description': """
        Complete campus, building, room and facility management
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base',
        'unicore_security',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/unicore_room_type_data.xml',
        'data/unicore_facility_type_data.xml',
        'report/unicore_campus_report.xml',
        'views/unicore_campus_ext_views.xml',
        'views/unicore_building_views.xml',
        'views/unicore_floor_views.xml',
        'views/unicore_room_views.xml',
        'views/unicore_facility_views.xml',
        'views/unicore_campus_kanban_views.xml',
        'menus/unicore_campus_menus.xml',
        'views/unicore_campus_view_mode_ext.xml',
        'views/unicore_campus_cleanup.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
