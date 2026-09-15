"""Client for communicating with the independent AI Parser application.

This module handles sending order packages (messages + attachments) from
the Telegram session to the external AI Parser and processing responses.

The AI Parser is a SEPARATE APPLICATION. This client only handles HTTP
communication — no AI/OCR logic belongs here.
"""
import logging
import time

import requests

_logger = logging.getLogger(__name__)

CONFIG_AI_PARSER_URL = 'telegram_odoo_integration.ai_parser_url'
CONFIG_AI_PARSER_API_KEY = 'telegram_odoo_integration.ai_parser_api_key'

ATTACHMENT_SERVE_BASE = '/ai_parser/attachment/'
ATTACHMENT_TOKEN_TTL_SECONDS = 900  # 15 minutes


class AIParserClient:
    """Communicates with the external AI Parser application."""

    def __init__(self, env):
        self.env = env

    def get_parser_url(self):
        """Return the AI Parser base URL."""
        return self.env['ir.config_parameter'].sudo().get_param(
            CONFIG_AI_PARSER_URL, '').strip().rstrip('/')

    def get_api_key(self):
        """Return the API key for the AI Parser."""
        return self.env['ir.config_parameter'].sudo().get_param(
            CONFIG_AI_PARSER_API_KEY, '').strip()

    def _get_attachment_base_url(self):
        """Return the base URL for serving attachments to the AI Parser."""
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '').strip().rstrip('/')
        return base_url

    def submit_order(self, session):
        """Send a complete order package to the AI Parser.

        :param session: telegram.order.session recordset (single record)
        :return: dict with 'status' key at minimum
        :raises: requests.RequestException on network errors
        """
        parser_url = self.get_parser_url()
        if not parser_url:
            raise ValueError(
                'AI Parser URL is not configured. '
                'Set it in Settings > Telegram > AI Parser URL.'
            )

        api_key = self.get_api_key()
        base_url = self._get_attachment_base_url()

        payload = self._build_request_payload(session, base_url)

        headers = {
            'Content-Type': 'application/json',
        }
        if api_key:
            headers['Authorization'] = 'Bearer %s' % api_key

        endpoint = '%s/api/v1/parse-order' % parser_url
        _logger.info(
            'Submitting session %s to AI Parser at %s '
            '(request_id=%s, messages=%d, attachments=%d)',
            session.session_id, endpoint, payload['request_id'],
            len(payload['messages']), len(payload['attachments']))

        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    def query_status(self, request_id):
        """Query the AI Parser for the status of a previous request.

        :param request_id: the request_id returned by submit_order
        :return: dict with 'status' key
        """
        parser_url = self.get_parser_url()
        if not parser_url:
            raise ValueError('AI Parser URL is not configured.')

        api_key = self.get_api_key()
        headers = {}
        if api_key:
            headers['Authorization'] = 'Bearer %s' % api_key

        endpoint = '%s/api/v1/status/%s' % (parser_url, request_id)
        response = requests.get(
            endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def _build_request_payload(self, session, base_url):
        """Build the JSON payload for the AI Parser."""
        messages = []
        for msg in session.message_ids.sorted(lambda m: m.sequence):
            messages.append({
                'text': msg.message_text,
                'sequence': msg.sequence,
            })

        attachments = []
        for att in session.attachment_ids.sorted(lambda a: a.sequence):
            secure_url = '%s%s%s' % (
                base_url, ATTACHMENT_SERVE_BASE, att.secure_token)
            attachments.append({
                'filename': att.filename,
                'mime_type': att.mime_type,
                'file_size': att.file_size,
                'file_hash': att.file_hash,
                'download_url': secure_url,
                'secure_token': att.secure_token,
            })

        return {
            'request_id': session.request_id,
            'session_id': session.session_id,
            'staff_id': session.staff_id.id,
            'staff_name': session.telegram_username or session.staff_id.name,
            'channel': 'telegram',
            'messages': messages,
            'attachments': attachments,
            'metadata': {
                'source': 'telegram',
                'telegram_username': session.telegram_username,
                'submitted_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            },
        }
