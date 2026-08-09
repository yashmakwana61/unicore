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
        data = self.env['telegram.message'].sudo()._read_group(
            [('order_id', 'in', self.ids)],
            ['order_id'],
            ['order_id:count'],
        )
        count_map = {
            order_id.id: count
            for order_id, count in data
            if order_id
        }
        for order in self:
            order.telegram_message_count = count_map.get(order.id, 0)
