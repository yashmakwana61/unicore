"""Business logic for the Telegram -> Sales Order integration.

The service is a plain Python class (no ORM model) so it is easy to unit
test and does not pollute the Odoo model registry. It receives an ``env``
and performs all writes with explicitly scoped ``sudo()`` calls because it
runs in the context of the public webhook route.
"""
import logging

import requests

from odoo.addons.telegram_odoo_integration.models.telegram_parser import (
    TelegramOrderParser,
)

_logger = logging.getLogger(__name__)

CONFIG_BOT_TOKEN = 'telegram_odoo_integration.bot_token'
CONFIG_ALLOWED_CHAT_ID = 'telegram_odoo_integration.allowed_chat_id'


class TelegramBotService:
    """Coordinates incoming Telegram updates and Sales Order creation."""

    def __init__(self, env):
        self.env = env

    # ------------------------------------------------------------------ #
    # Configuration helpers
    # ------------------------------------------------------------------ #
    def get_bot_token(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            CONFIG_BOT_TOKEN, '').strip()

    def get_allowed_chat_id(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            CONFIG_ALLOWED_CHAT_ID, '').strip()

    def is_chat_allowed(self, chat_id):
        """Return True only for the configured chat id.

        If no chat id is configured, no one is allowed (fail-closed).
        """
        allowed = self.get_allowed_chat_id()
        if not allowed:
            _logger.warning(
                'No allowed chat id configured in %s; rejecting all chats',
                CONFIG_ALLOWED_CHAT_ID)
            return False
        return str(chat_id or '') == str(allowed).strip()

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def process_update(self, data):
        """Handle one Telegram update dict.

        :return: JSON-serialisable dict for the webhook response.
        """
        data = dict(data or {})
        # Tolerate a JSON-RPC style envelope: {"params": {...}}
        if 'params' in data and not data.get('update_id'):
            data = dict(data.get('params') or {})

        update_id = data.get('update_id')
        message = data.get('message') or data.get('edited_message') or {}
        chat = message.get('chat') or {}
        chat_id = str(chat.get('id') or '')
        from_user = message.get('from') or {}
        username = (
            from_user.get('username')
            or from_user.get('first_name')
            or str(from_user.get('id') or '')
        )
        text = message.get('text') or ''

        # 1. Audit: persist every raw update regardless of the outcome.
        log = self.env['telegram.message'].sudo()._log_update(data)

        # 2. Security layer: only allow the configured chat id.
        if not self.is_chat_allowed(chat_id):
            _logger.warning(
                'Rejected Telegram update %s from unauthorized chat %s',
                update_id, chat_id)
            log.write({
                'state': 'rejected',
                'error_message': 'Unauthorized chat id',
            })
            self.send_telegram_message(
                chat_id,
                'You are not authorized to place orders through this bot.')
            return {'success': False, 'error': 'Unauthorized chat id'}

        # 3. Ignore non-text updates (photos, stickers, voice notes, ...).
        if not text:
            log.write({'state': 'ignored'})
            return {'success': False, 'error': 'No text message',
                    'ignored': True}

        # Bonus: friendly help for the /start and /help commands.
        if text.strip().lower() in ('/start', '/help'):
            help_text = (
                'Welcome! To place an order send:\n'
                'Order: Product Qty:2 Price:100\n\n'
                'Multiple products (comma separated):\n'
                'Order: Laptop Qty:1 Price:50000, Mouse Qty:2 Price:300'
            )
            log.write({'state': 'ignored'})
            self.send_telegram_message(chat_id, help_text)
            return {'success': True, 'message': 'help sent', 'ignored': True}

        # 4. Parse the order message.
        items, parse_error = TelegramOrderParser.parse(text)
        if parse_error:
            _logger.info(
                'Telegram message %s could not be parsed: %s',
                log.id, parse_error)
            log.write({'state': 'error', 'error_message': parse_error})
            self.send_telegram_message(chat_id, parse_error)
            return {'success': False, 'error': parse_error}

        # 5. Identify or create the customer.
        partner = self._find_or_create_partner(username, chat_id)

        # 6. Create the Sales Order (with all parsed lines).
        try:
            order = self.create_sale_order(partner, items)
        except Exception as exc:  # noqa: BLE001 - report any failure to the user
            _logger.exception(
                'Failed to create Sales Order from Telegram message %s',
                log.id)
            log.write({
                'state': 'error',
                'error_message': str(exc),
            })
            self.send_telegram_message(
                chat_id,
                'Sorry, your order could not be created. Error: %s' % exc)
            return {'success': False, 'error': str(exc)}

        log.write({
            'state': 'order_created',
            'partner_id': partner.id,
            'order_id': order.id,
        })
        _logger.info(
            'Sales Order %s created from Telegram message %s (chat %s)',
            order.name, log.id, chat_id)

        reply = 'Order created successfully: %s' % order.name
        self.send_telegram_message(chat_id, reply)
        return {
            'success': True,
            'message': reply,
            'order_name': order.name,
            'order_id': order.id,
            'total': order.amount_total,
        }

    # ------------------------------------------------------------------ #
    # Customer handling
    # ------------------------------------------------------------------ #
    def _find_or_create_partner(self, username, chat_id):
        """Return the partner for a Telegram user, creating it if needed."""
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([
            '|',
            ('telegram_username', '=', username),
            ('telegram_chat_id', '=', chat_id),
        ], limit=1)
        if not partner:
            partner = Partner.search([('name', '=', username)], limit=1)

        if partner:
            write_vals = {}
            if username and not partner.telegram_username:
                write_vals['telegram_username'] = username
            if chat_id and not partner.telegram_chat_id:
                write_vals['telegram_chat_id'] = chat_id
            if write_vals:
                partner.write(write_vals)
            return partner

        partner = Partner.create({
            'name': username or 'Telegram User',
            'telegram_username': username,
            'telegram_chat_id': chat_id,
        })
        _logger.info('Created partner %s for Telegram user %s',
                     partner.id, username)
        return partner

    # ------------------------------------------------------------------ #
    # Product handling
    # ------------------------------------------------------------------ #
    def _find_or_create_product(self, name, price):
        """Return the product matching ``name``, creating it if needed."""
        Product = self.env['product.product'].sudo()
        product = Product.search([('name', '=', name)], limit=1)
        if product:
            return product

        template = self.env['product.template'].sudo().create({
            'name': name,
            'list_price': float(price),
            'type': 'consu',
            'sale_ok': True,
            'purchase_ok': False,
        })
        product = template.product_variant_ids[:1]
        _logger.info('Created product %s (id %s) with list price %s',
                     product.name, product.id, price)
        return product

    # ------------------------------------------------------------------ #
    # Sales Order creation
    # ------------------------------------------------------------------ #
    def _get_pricelist(self, partner):
        """Return a pricelist for the order (partner > company > first).

        Defensive across Odoo versions: ``res.company.property_product_pricelist``
        was removed in Odoo 19 (it exists in 16/17), so it is only accessed
        when the field is present.
        """
        pricelist = partner.sudo().property_product_pricelist
        company = self.env.company
        if not pricelist and hasattr(company, 'property_product_pricelist'):
            pricelist = company.property_product_pricelist
        if not pricelist:
            pricelist = self.env['product.pricelist'].sudo().search(
                [('active', '=', True)], limit=1)
        return pricelist

    def create_sale_order(self, partner, items):
        """Create a draft ``sale.order`` with one line per parsed item."""
        lines = []
        for item in items:
            product = self._find_or_create_product(item['name'], item['price'])
            lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': float(item['qty']),
                'price_unit': float(item['price']),
            }))

        order_vals = {
            'partner_id': partner.id,
            'pricelist_id': self._get_pricelist(partner).id,
            'company_id': self.env.company.id,
            'note': 'Order created automatically from a Telegram message.',
            'order_line': lines,
        }
        order = self.env['sale.order'].sudo().create(order_vals)
        _logger.info('Sales Order %s created for partner %s with %d line(s)',
                     order.name, partner.id, len(lines))
        return order

    # ------------------------------------------------------------------ #
    # Telegram Bot API
    # ------------------------------------------------------------------ #
    def send_telegram_message(self, chat_id, text):
        """Send a reply to ``chat_id`` through the Telegram Bot API.

        :return: parsed JSON response dict or ``None`` on failure.
        """
        token = self.get_bot_token()
        if not token:
            _logger.error(
                'Telegram bot token not configured (%s); cannot send reply',
                CONFIG_BOT_TOKEN)
            return None
        if not chat_id:
            _logger.warning('No chat id available to send Telegram reply')
            return None

        url = 'https://api.telegram.org/bot%s/sendMessage' % token
        try:
            response = requests.post(
                url,
                json={'chat_id': chat_id, 'text': text},
                timeout=10,
            )
            response.raise_for_status()
            _logger.debug('Telegram reply sent to chat %s: %s', chat_id, text)
            return response.json()
        except requests.RequestException as exc:
            _logger.error('Failed to send Telegram reply to chat %s: %s',
                          chat_id, exc)
            return None
