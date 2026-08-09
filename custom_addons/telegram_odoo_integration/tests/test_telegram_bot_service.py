"""Integration tests for the Telegram bot service.

The outbound Telegram HTTP call is mocked so tests never hit the real API.
"""
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.telegram_odoo_integration.models.telegram_bot_service import (
    CONFIG_ALLOWED_CHAT_ID,
    CONFIG_BOT_TOKEN,
    TelegramBotService,
)


@tagged('post_install', '-at_install')
class TestTelegramBotService(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].set_param(CONFIG_BOT_TOKEN, 'TEST_TOKEN')
        self.env['ir.config_parameter'].set_param(CONFIG_ALLOWED_CHAT_ID, '123456')

    def _mock_telegram_api(self):
        patcher = patch(
            'odoo.addons.telegram_odoo_integration.models.'
            'telegram_bot_service.requests.post')
        mock_post = patcher.start()
        self.addCleanup(patcher.stop)
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'ok': True}
        return mock_post

    def test_valid_message_creates_sale_order(self):
        self._mock_telegram_api()
        update = {
            'update_id': 1001,
            'message': {
                'chat': {'id': 123456},
                'from': {'id': 42, 'username': 'john_doe'},
                'text': 'Order: Laptop Qty:2 Price:50000',
            },
        }
        service = TelegramBotService(self.env)
        result = service.process_update(update)

        self.assertTrue(result['success'])
        self.assertIn('Order created successfully', result['message'])

        order = self.env['sale.order'].browse(result['order_id'])
        self.assertTrue(order)
        self.assertEqual(order.partner_id.name, 'john_doe')
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line[0].product_uom_qty, 2.0)
        self.assertEqual(order.order_line[0].price_unit, 50000.0)

        # Chat history is persisted and linked to the order.
        log = self.env['telegram.message'].search(
            [('update_id', '=', '1001')], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.state, 'order_created')
        self.assertEqual(log.order_id, order)
        self.assertEqual(log.partner_id, order.partner_id)

    def test_multiple_products_creates_multiple_lines(self):
        self._mock_telegram_api()
        update = {
            'update_id': 1002,
            'message': {
                'chat': {'id': 123456},
                'from': {'id': 43, 'username': 'jane_doe'},
                'text': 'Order: Laptop Qty:1 Price:50000, Mouse Qty:2 Price:300',
            },
        }
        result = TelegramBotService(self.env).process_update(update)
        self.assertTrue(result['success'])
        order = self.env['sale.order'].browse(result['order_id'])
        self.assertEqual(len(order.order_line), 2)

    def test_unauthorized_chat_is_rejected(self):
        mock_post = self._mock_telegram_api()
        update = {
            'update_id': 1003,
            'message': {
                'chat': {'id': 999999},
                'from': {'id': 44, 'username': 'intruder'},
                'text': 'Order: Laptop Qty:1 Price:100',
            },
        }
        result = TelegramBotService(self.env).process_update(update)

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Unauthorized chat id')
        # No order should exist for the intruder.
        self.assertEqual(self.env['sale.order'].search_count([]), 0)
        log = self.env['telegram.message'].search(
            [('update_id', '=', '1003')], limit=1)
        self.assertEqual(log.state, 'rejected')
        # The user is still notified through Telegram.
        mock_post.assert_called_once()

    def test_invalid_format_replies_with_help(self):
        mock_post = self._mock_telegram_api()
        update = {
            'update_id': 1004,
            'message': {
                'chat': {'id': 123456},
                'from': {'id': 45, 'username': 'john_doe'},
                'text': 'I want a laptop',
            },
        }
        result = TelegramBotService(self.env).process_update(update)
        self.assertFalse(result['success'])
        self.assertIn('Invalid format', result['error'])
        # The invalid format help message is sent back to the user.
        sent_text = mock_post.call_args.kwargs['json']['text']
        self.assertIn('Invalid format', sent_text)

    def test_existing_partner_is_reused(self):
        self._mock_telegram_api()
        partner = self.env['res.partner'].create({
            'name': 'john_doe',
            'telegram_username': 'john_doe',
            'telegram_chat_id': '123456',
        })
        update = {
            'update_id': 1005,
            'message': {
                'chat': {'id': 123456},
                'from': {'id': 42, 'username': 'john_doe'},
                'text': 'Order: Keyboard Qty:1 Price:500',
            },
        }
        result = TelegramBotService(self.env).process_update(update)
        self.assertTrue(result['success'])
        order = self.env['sale.order'].browse(result['order_id'])
        self.assertEqual(order.partner_id, partner)
        self.assertEqual(
            self.env['res.partner'].search_count(
                [('telegram_username', '=', 'john_doe')]), 1)
