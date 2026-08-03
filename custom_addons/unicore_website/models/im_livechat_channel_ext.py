from odoo import _, fields, models


class ImLivechatChannelExt(models.Model):
    _inherit = 'im_livechat.channel'

    unicore_admissions_channel = fields.Boolean(
        string='UniCore Admissions Channel',
        help='Mark this livechat channel for admissions enquiries.')