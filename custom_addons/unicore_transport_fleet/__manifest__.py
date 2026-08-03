{
    'name': 'Transport Fleet Integration',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Bridge UniCore transport vehicles into Odoo Fleet management',
    'description': """
        Transport Fleet Integration
        ===========================

        Bridges UniCore's transport vehicle records into Odoo's native Fleet
        management module so university fleet vehicles can be tracked with
        standard fleet features: assignment logs, service contracts, odometer
        tracking, and driver management.

        Key behaviour:
        - A ``fleet.vehicle`` is auto-created when a UniCore transport vehicle
          is created, and kept in sync.
        - Key fields (license plate, driver, seating capacity, fuel type,
          colour, acquisition date) are mirrored bidirectionally.
        - A smart button on the transport vehicle form opens the linked fleet
          vehicle, and vice versa.
        - The Fleet app is made visible to UniCore transport staff via implied
          ``fleet.group_user``.

        No core ``unicore_transport`` or ``fleet`` logic is modified.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'fleet',
        'unicore_transport',
        'unicore_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/fleet_data.xml',
        'views/transport_vehicle_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_transport_fleet,static/description/icon.png',
    'installable': True,
    'application': False,
    'auto_install': False,
}