import json
import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_API_URL = 'https://opencode.ai/zen/v1/chat/completions'
DEFAULT_MODEL = 'deepseek-v4-0324'
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048


class OacisAIProvider(models.AbstractModel):
    """Utility abstract model that encapsulates all communication with the
    OpenCode Zen (OpenAI-compatible) API.  Any model that needs AI features
    can call the helper methods defined here via ``self.env['oacis.ai.provider']``.
    """
    _name = 'oacis.ai.provider'
    _description = 'Oacis AI Provider'

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    @api.model
    def _get_api_key(self):
        """Return the configured API key or raise."""
        key = self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.api_key', default='',
        )
        if not key:
            raise UserError(_(
                'OpenCode Zen API key is not configured. '
                'Please go to Settings → Oacis AI and enter your API key.',
            ))
        return key

    @api.model
    def _get_api_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.api_url', default=DEFAULT_API_URL,
        )

    @api.model
    def _get_model(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.model', default=DEFAULT_MODEL,
        )

    @api.model
    def _get_temperature(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.temperature', default=str(DEFAULT_TEMPERATURE),
        )
        try:
            return float(val)
        except (ValueError, TypeError):
            return DEFAULT_TEMPERATURE

    @api.model
    def _get_max_tokens(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.max_tokens', default=str(DEFAULT_MAX_TOKENS),
        )
        try:
            return int(val)
        except (ValueError, TypeError):
            return DEFAULT_MAX_TOKENS

    # ------------------------------------------------------------------
    # Core API call
    # ------------------------------------------------------------------

    @api.model
    def _call_api(self, messages, **kwargs):
        """Send a chat-completion request to the OpenCode Zen API.

        :param messages: list of dicts ``[{'role': '...', 'content': '...'}]``
        :param kwargs: optional overrides for *model*, *temperature*,
                       *max_tokens*, or any extra body params.
        :returns: the assistant's reply text
        :raises UserError: on network or API errors
        """
        api_key = self._get_api_key()
        url = kwargs.pop('url', None) or self._get_api_url()
        model = kwargs.pop('model', None) or self._get_model()
        temperature = kwargs.pop('temperature', None)
        if temperature is None:
            temperature = self._get_temperature()
        max_tokens = kwargs.pop('max_tokens', None) or self._get_max_tokens()

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        payload.update(kwargs)

        _logger.info(
            'Oacis AI → calling %s  model=%s  messages=%d',
            url, model, len(messages),
        )

        try:
            resp = requests.post(
                url, headers=headers, json=payload, timeout=120,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            raise UserError(_(
                'The AI service did not respond in time. Please try again.',
            ))
        except requests.exceptions.ConnectionError:
            raise UserError(_(
                'Could not connect to the AI service. '
                'Please check your network and API URL configuration.',
            ))
        except requests.exceptions.HTTPError as exc:
            body = ''
            try:
                body = exc.response.text
            except Exception:
                pass
            _logger.error('Oacis AI HTTP error: %s — %s', exc, body)
            raise UserError(_(
                'AI service returned an error (%(status)s). '
                'Details: %(body)s',
                status=exc.response.status_code,
                body=body[:500],
            ))

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            raise UserError(_('Unexpected response from the AI service.'))

        # Standard OpenAI-compatible response structure
        try:
            return data['choices'][0]['message']['content']
        except (KeyError, IndexError):
            _logger.error('Oacis AI unexpected payload: %s', data)
            raise UserError(_(
                'The AI service returned an unexpected response structure.',
            ))

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    @api.model
    def generate_text(self, prompt, system_prompt=None):
        """Simple one-shot text generation.

        :param prompt: the user prompt
        :param system_prompt: optional system-level instruction
        :returns: generated text string
        """
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        return self._call_api(messages)

    @api.model
    def rewrite_text(self, text, instruction='Improve this text'):
        """Rewrite *text* according to *instruction*."""
        system_prompt = (
            'You are a professional writing assistant. '
            'Follow the user\'s instruction to rewrite the given text. '
            'Return ONLY the rewritten text, nothing else.'
        )
        user_prompt = f'Instruction: {instruction}\n\nText:\n{text}'
        return self._call_api([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ])

    @api.model
    def summarize_text(self, text):
        """Return a concise summary of *text*."""
        system_prompt = (
            'You are a summarisation assistant. '
            'Provide a concise summary of the following text. '
            'Return ONLY the summary, nothing else.'
        )
        return self._call_api([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': text},
        ])

    @api.model
    def chat(self, messages):
        """Multi-turn conversation.

        :param messages: full conversation history as list of dicts.
        :returns: assistant reply text
        """
        system_msg = {
            'role': 'system',
            'content': (
                'You are Oacis AI, a helpful and friendly assistant '
                'integrated into the Oacis Education Management System. '
                'Answer questions about academics, administration, '
                'assignments, exams, fees, or any other education-related '
                'topics. Be concise and professional.'
            ),
        }
        full_messages = [system_msg] + messages
        return self._call_api(full_messages)
