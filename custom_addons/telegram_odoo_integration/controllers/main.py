"""HTTP controllers for the Telegram integration."""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.telegram_odoo_integration.models.telegram_bot_service import (
    TelegramBotService,
)

_logger = logging.getLogger(__name__)


class TelegramWebhook(http.Controller):
    """Public webhook endpoint receiving Telegram bot updates."""

    @http.route('/telegram/webhook', type='json', auth='public', csrf=False,
                methods=['POST'])
    def telegram_webhook(self, **kwargs):
        """Entry point for Telegram updates.

        Telegram POSTs a *plain* JSON object (e.g. ``{"update_id": ...,
        "message": {...}}``), not a JSON-RPC envelope. Odoo's ``type='json'``
        routing parses the body but only forwards a ``params`` member to the
        method, so the full update is read explicitly through
        ``request.get_json_data()``. Any ``kwargs`` (e.g. from a JSON-RPC
        envelope) are merged as a fallback.

        The returned dict is wrapped by the framework in the standard jsonrpc
        envelope; Telegram ignores the response body, the user-facing reply is
        sent back to the chat through the Telegram Bot API by the service.
        """
        _logger.info('Telegram webhook received')

        try:
            data = request.get_json_data() or {}
        except Exception:  # noqa: BLE001 - never let the webhook crash
            _logger.exception('Could not parse Telegram webhook body')
            return {'success': False, 'error': 'Invalid JSON body'}
        data.update(kwargs)

        service = TelegramBotService(request.env)
        return service.process_update(data)
