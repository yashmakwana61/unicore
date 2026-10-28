from odoo import fields, models


class ImLivechatChannelExt(models.Model):
    _inherit = 'im_livechat.channel'

    edicai_admissions_channel = fields.Boolean(
        string='Edicai Admissions Channel',
        help='Mark this livechat channel for admissions enquiries.')
