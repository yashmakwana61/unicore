{
    'name': 'Hostel',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'University hostel and accommodation '
               'management for student residences',
    'description': """
        UniCore Hostel provides complete university
        hostel management:

        - Hostel Blocks: define residential blocks
          with warden details and facilities
        - Rooms: room types, capacity, amenities,
          current occupancy tracking
        - Room Allocations: student-to-room
          assignment per academic year with
          check-in and check-out processing
        - Hostel Fees: per-semester hostel charges
          tracked separately from tuition fees
        - Maintenance Requests: students or wardens
          can log maintenance issues with priority
          and resolution tracking
        - Occupancy Dashboard: real-time room
          availability across all blocks

        Appears as a dedicated app in the Odoo
        home screen.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base', 'unicore_security',
        'unicore_campus', 'unicore_academic',
        'unicore_calendar', 'unicore_student',
        'mail',
    ],
    'data': [
        'security/unicore_hostel_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_hostel_sequence_data.xml',
        'views/unicore_hostel_block_views.xml',
        'views/unicore_hostel_room_views.xml',
        'views/unicore_hostel_allocation_views.xml',
        'views/unicore_hostel_maintenance_views.xml',
        'views/hostel_search_phase1.xml',
        'menus/unicore_hostel_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_hostel,'
                'static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
