from odoo import fields, models


class WebsiteExt(models.Model):
    _inherit = 'website'

    edicai_admissions_page = fields.Boolean(
        string='Edicai Admissions Page',
        help='Mark this website as hosting the Edicai admissions portal.')
    admissions_page_url = fields.Char(
        string='Admissions Page URL',
        help='URL path for the admissions enquiry page.')
