from odoo import fields, models


class WebsiteExt(models.Model):
    _inherit = 'website'

    oacis_admissions_page = fields.Boolean(
        string='Oacis Admissions Page',
        help='Mark this website as hosting the Oacis admissions portal.')
    admissions_page_url = fields.Char(
        string='Admissions Page URL',
        help='URL path for the admissions enquiry page.')
