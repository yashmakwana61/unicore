"""res.partner extension: portal-callable Telegram OTP helpers.

Kept in its own file so the base ``res_partner.py`` stays untouched.
Portal controllers call these methods on the CURRENT user's partner with the
user's own rights (no sudo on user data)::

    otp = request.env.user.partner_id.action_generate_telegram_otp()
    # show ``otp`` once in the portal, then discard it

    request.env.user.partner_id.action_unlink_telegram_chat()
"""
from odoo import api, fields, models


class ResPartnerTelegramLink(models.Model):
    _inherit = 'res.partner'

    telegram_chat_link_id = fields.Many2one(
        'telegram.chat.link', string='Telegram Link',
        compute='_compute_telegram_chat_link_id', store=False)

    @api.depends('telegram_chat_id')
    def _compute_telegram_chat_link_id(self):
        Link = self.env['telegram.chat.link']
        for partner in self:
            link = Link.search([
                ('partner_id', '=', partner.id),
            ], limit=1) if partner.id else False
            partner.telegram_chat_link_id = link.id if link else False

    def action_generate_telegram_otp(self):
        """Issue a Telegram linking OTP for this contact; return it once."""
        self.ensure_one()
        return self.env['telegram.chat.link'].generate_otp(self)

    def action_unlink_telegram_chat(self):
        """Unlink any verified Telegram chat bound to this contact."""
        self.ensure_one()
        links = self.env['telegram.chat.link'].search([
            ('partner_id', '=', self.id),
            ('verified', '=', True),
        ])
        if links:
            links.action_unlink()
        return True
