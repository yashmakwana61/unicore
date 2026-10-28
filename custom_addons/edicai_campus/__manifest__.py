{
    'name': 'Edicai Campus Management',
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
        'edicai_base',
        'edicai_security',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/edicai_room_type_data.xml',
        'data/edicai_facility_type_data.xml',
        'report/edicai_campus_report.xml',
        'views/edicai_campus_ext_views.xml',
        'views/edicai_building_views.xml',
        'views/edicai_floor_views.xml',
        'views/edicai_room_views.xml',
        'views/edicai_facility_views.xml',
        'views/edicai_campus_kanban_views.xml',
        'menus/edicai_campus_menus.xml',
        'views/edicai_campus_view_mode_ext.xml',
        'views/edicai_campus_cleanup.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
