from odoo import fields, models


class WebsiteExt(models.Model):
    _inherit = 'website'

    unicore_admissions_page = fields.Boolean(
        string='UniCore Admissions Page',
        help='Mark this website as hosting the UniCore admissions portal.')
    admissions_page_url = fields.Char(
        string='Admissions Page URL',
        help='URL path for the admissions enquiry page.')
