"""Small extension of sale.order to expose Telegram message statistics."""
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    telegram_message_count = fields.Integer(
        string='Telegram Messages',
        compute='_compute_telegram_message_count',
    )

    @api.depends('name')
    def _compute_telegram_message_count(self):
        for order in self:
            count = self.env['telegram.message'].sudo().search_count([
                '|',
                ('order_id', '=', order.id),
                ('session_id.sale_order_id', '=', order.id),
            ])
            order.telegram_message_count = count

    def action_view_telegram_messages(self):
        self.ensure_one()
        return {
            'name': 'Telegram Messages',
            'type': 'ir.actions.act_window',
            'res_model': 'telegram.message',
            'view_mode': 'list,form',
            'domain': ['|',
                       ('order_id', '=', self.id),
                       ('session_id.sale_order_id', '=', self.id)],
        }
