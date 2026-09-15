{
    'name': 'Admission Fees Bridge',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Bridge between admission and fee management',
    'description': """
        Auto-generates the admission fee invoice when an applicant's offer is
        accepted (fee pending) and confirms the admission automatically once
        the invoice is fully paid.

        This bridge module exists because oacis_fees already depends on
        oacis_admission: neither module can extend the other without creating a
        circular dependency, so the integration lives here instead.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'oacis_admission',
        'oacis_fees',
    ],
    'data': [
        'views/oacis_admission_applicant_fee_views_ext.xml',
        'views/oacis_fee_invoice_admission_views_ext.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
