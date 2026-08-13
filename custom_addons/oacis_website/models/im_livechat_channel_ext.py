from odoo import fields, models


class ImLivechatChannelExt(models.Model):
    _inherit = 'im_livechat.channel'

    oacis_admissions_channel = fields.Boolean(
        string='Oacis Admissions Channel',
        help='Mark this livechat channel for admissions enquiries.')
