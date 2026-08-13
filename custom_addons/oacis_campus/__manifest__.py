{
    'name': 'Oacis Campus Management',
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
        'oacis_base',
        'oacis_security',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/oacis_room_type_data.xml',
        'data/oacis_facility_type_data.xml',
        'report/oacis_campus_report.xml',
        'views/oacis_campus_ext_views.xml',
        'views/oacis_building_views.xml',
        'views/oacis_floor_views.xml',
        'views/oacis_room_views.xml',
        'views/oacis_facility_views.xml',
        'views/oacis_campus_kanban_views.xml',
        'menus/oacis_campus_menus.xml',
        'views/oacis_campus_view_mode_ext.xml',
        'views/oacis_campus_cleanup.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
