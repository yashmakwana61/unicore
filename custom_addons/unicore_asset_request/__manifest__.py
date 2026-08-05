# -*- coding: utf-8 -*-
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
    'author': 'UniCore',
    'website': 'https://unicore.example.com',
    'depends': [
        'unicore_campus',
        'unicore_faculty_profile',
        'unicore_security',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/unicore_asset_request_record_rules.xml',
        'data/unicore_asset_request_sequence_data.xml',
        'views/unicore_asset_views.xml',
        'views/unicore_asset_request_views.xml',
        'menus/unicore_asset_request_menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}
