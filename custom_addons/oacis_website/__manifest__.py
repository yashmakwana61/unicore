{
    'name': 'Admissions Website',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Bridge Oacis admissions into Odoo website, livechat and CRM',
    'description': """
        Admissions Website
        ==================

        Bridges Oacis's admissions process into Odoo's native Website,
        Live Chat and CRM modules so prospective students can explore
        programmes, chat with admissions staff, and submit enquiries
        through a standard website.

        Key behaviour:
        - A ``website.website`` page is created for the admissions portal
          with programme listings and an enquiry form.
        - An ``im_livechat.channel`` is auto-created for admissions
          live chat so visitors can talk to the admissions team.
        - Enquiries submitted via the website auto-create ``crm.lead``
          records in the admissions CRM pipeline.
        - Smart buttons on the CRM lead open the linked website page
          and the admissions enquiry.
        - No core ``oacis_admission``, ``website``, ``im_livechat``,
          or ``crm`` logic is modified.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'website',
        'im_livechat',
        'crm',
        'oacis_admission',
        'oacis_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/website_data.xml',
        'views/website_views.xml',
        'views/im_livechat_views.xml',
        'views/crm_lead_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'oacis_website,static/description/icon.png',
    'installable': True,
    'application': False,
    'auto_install': False,
}
