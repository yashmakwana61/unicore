{
    'name': 'UniCore Campus Management',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Complete campus, building, room and facility management',
    'description': """
UniCore Campus Management
=========================

Complete campus infrastructure management module for UniCore ERP.

This module extends the base campus model with full infrastructure
management including buildings, floors, rooms, and facilities.

Key features:
- Multi-building campus management with floor-by-floor breakdown
- Room inventory with type classification and amenity tracking
- Facility management (sports, medical, canteen, etc.)
- Campus state workflow (Draft → Operational → Suspended → Closed)
- Smart dashboard with building/room/facility counts
- Printable campus infrastructure summary report
- Full multi-company and multi-campus data isolation
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'LGPL-3',
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
        'menus/unicore_campus_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
