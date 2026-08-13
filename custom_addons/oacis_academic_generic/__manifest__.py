{
    'name': 'Oacis Generic Academic Structure',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Generic self-referencing academic unit tree (Faculty, Department, Grade Level, Wing...)',
    'description': """
        Generic hierarchical academic units that replace the rigid
        Faculty -> Department -> Program chain for non-university institution
        types (K-12 schools, training institutes, academies).

        This module is ADDITIVE ONLY: it introduces oacis.academic.unit as a
        depth-unlimited, self-referencing, type-configurable tree and does not
        modify oacis_academic in any way. The terminal node (program / cohort /
        batch) attaches to this tree in a later phase.
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
        'data/oacis_academic_unit_type_data.xml',
        'views/oacis_academic_unit_type_views.xml',
        'views/oacis_academic_unit_views.xml',
        'menus/oacis_academic_generic_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
