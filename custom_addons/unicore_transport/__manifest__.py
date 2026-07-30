{
    'name': 'Transport',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'University student transport '
               'management with routes and passes',
    'description': """
        UniCore Transport provides complete university
        transport management:

        - Vehicles: bus and van fleet with capacity,
          driver, insurance and fitness certificate
          tracking
        - Routes: named transport routes with ordered
          stop sequences and timing
        - Route Stops: pick-up/drop points along
          each route with distance from campus
        - Transport Passes: student subscription to
          a route for an academic term with fee
          tracking and pass number generation
        - Trip Logs: daily trip records for
          operational tracking and reporting
        - Transport Fees: semester-wise charges per
          route/stop with collection tracking

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
        'security/unicore_transport_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_transport_sequence_data.xml',
        'views/unicore_transport_vehicle_views.xml',
        'views/unicore_transport_route_views.xml',
        'views/unicore_transport_pass_views.xml',
        'views/unicore_transport_trip_views.xml',
        'views/transport_search_phase1.xml',
        'menus/unicore_transport_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_transport,'
                'static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
