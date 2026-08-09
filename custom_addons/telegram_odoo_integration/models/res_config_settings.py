"""Add Telegram configuration to the Odoo Settings page."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    telegram_bot_token = fields.Char(
        string='Telegram Bot Token',
        config_parameter='telegram_odoo_integration.bot_token',
        help='Token obtained from @BotFather when creating the bot on '
             'Telegram.')
    telegram_allowed_chat_id = fields.Char(
        string='Allowed Chat ID',
        config_parameter='telegram_odoo_integration.allowed_chat_id',
        help='Only messages coming from this Telegram chat id will be '
             'processed. Leave empty to reject all chats (fail-closed). '
             'Find your chat id by messaging @userinfobot on Telegram.')
