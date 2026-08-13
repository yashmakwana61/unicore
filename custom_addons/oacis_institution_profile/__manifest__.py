{
    'name': 'UniCore Institution Profile',
    'version': '19.0.1.3.0',
    'category': 'Education',
    'summary': 'Institution type, terminology and feature profiles driving multi-entity behavior',
    'description': """
        Institution Profile turns the dormant res.company.university_type label into
        a real driver. One profile per institution configures:

          - institution_type      (university | college | school | training | academy | coaching)
          - academic_unit_levels  (which generic academic unit types the hierarchy may use)
          - calendar_mode         (semester | trimester | quarter | annual | rolling_batch)
          - grading_scheme        (default strategy; the Grading Scheme MODEL is Phase 2)
          - terminology_profile   (field-label substitutions; applied at setup, Phase 5)
          - feature toggles       (which optional modules are relevant)

        Phase 0 is ADDITIVE ONLY. The default "University - Legacy" profile preserves
        100% of current behavior, and res.company.institution_profile_id is nullable
        (unset = legacy university behavior). No existing module is modified.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base',
        'unicore_security',
        'unicore_academic_generic',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/unicore_institution_profile_data.xml',
        'data/unicore_institution_profile_templates.xml',
        'views/unicore_institution_feature_views.xml',
        'views/unicore_terminology_profile_views.xml',
        'views/unicore_grading_scheme_views.xml',
        'views/unicore_institution_profile_views.xml',
        'views/res_company_views.xml',
        'menus/unicore_institution_profile_menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
