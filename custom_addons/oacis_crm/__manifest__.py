{
    'name': 'Admissions CRM',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Bridge Oacis admission applicants into Odoo CRM pipeline',
    'description': """
        Admissions CRM
        ==============

        Mirrors Oacis admission applicants into Odoo's native CRM pipeline
        so the admissions team can track enquiries, schedule follow-ups
        (activities/emails), and report on the funnel using standard CRM
        views and reporting.

        Key behaviour:
        - A ``crm.lead`` (opportunity) is auto-created when an applicant is
          created and kept in sync with the applicant's state via a custom
          stage set.
        - Moving the lead's stage in the CRM updates the applicant state
          (best-effort, bypassing the guarded action methods so the CRM
          pipeline stays authoritative).
        - A smart button on the applicant form opens the linked lead.
        - The CRM app is made visible to Oacis admins and managers via
          implied ``sales_team.group_sale_salesman``.

        No core ``oacis_admission`` or ``crm`` logic is modified.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'crm',
        'oacis_admission',
        'oacis_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/crm_data.xml',
        'data/res_groups_data.xml',
        'views/admission_applicant_crm_views.xml',
        'views/crm_lead_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'oacis_crm,static/description/icon.png',
    'installable': True,
    'application': False,
    'auto_install': False,
}
