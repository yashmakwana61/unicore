{
    'name': 'Asset Request',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Equipment and facility request and approval workflow',
    'description': """
Asset Request Module
====================
Manage equipment and facility requests with an approval workflow.
Faculty and staff can request assets (projectors, lab equipment,
specialized tools, etc.) through a structured draft → submitted →
approved/rejected → fulfilled lifecycle.
    """,
    'author': 'Edicai',
    'website': 'https://edicai.example.com',
    'depends': [
        'edicai_campus',
        'edicai_faculty_profile',
        'edicai_security',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/edicai_asset_request_record_rules.xml',
        'data/edicai_asset_request_sequence_data.xml',
        'views/edicai_asset_views.xml',
        'views/edicai_asset_request_views.xml',
        'menus/edicai_asset_request_menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'license': 'OPL-1',

    'auto_install': False,
}
