import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from .edicai_ai_provider import ZEN_STATIC_MODELS

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    edicai_ai_api_key = fields.Char(
        string='API Key',
        config_parameter='edicai_ai.api_key',
        help='Your OpenCode Zen API key (or any OpenAI-compatible key).',
    )
    edicai_ai_api_url = fields.Char(
        string='API URL',
        config_parameter='edicai_ai.api_url',
        default='https://opencode.ai/zen/v1/chat/completions',
        help='Endpoint URL. For OpenCode Zen the per-model endpoint '
             '(chat / responses / messages) is chosen automatically; '
             'custom non-Zen URLs always use the OpenAI chat format.',
    )
    edicai_ai_model = fields.Selection(
        selection='_selection_edicai_ai_model',
        string='Model',
        config_parameter='edicai_ai.model',
        default='deepseek-v4-flash',
        help='OpenCode Zen model used for chatbot and text generation. '
             'Use "Refresh Models" to fetch the latest list.',
    )
    edicai_ai_system_prompt = fields.Char(
        string='Assistant Personality',
        config_parameter='edicai_ai.system_prompt',
        default=(
            'You are Edicai AI, a helpful and friendly assistant '
            'integrated into the Edicai Education Management System.'
        ),
        help='Default system instruction prepended to every chatbot/generation request.',
    )
    edicai_ai_temperature = fields.Float(
        string='Temperature',
        config_parameter='edicai_ai.temperature',
        default=0.7,
        help='Controls randomness: 0 = deterministic, 1 = very creative.',
    )
    edicai_ai_max_tokens = fields.Integer(
        string='Max Tokens',
        config_parameter='edicai_ai.max_tokens',
        default=2048,
        help='Maximum number of tokens in the AI response.',
    )
    edicai_ai_rate_limit = fields.Integer(
        string='Requests / user / hour',
        config_parameter='edicai_ai.rate_limit_per_hour',
        default=60,
        help='0 = unlimited. Protects against runaway usage/cost.',
    )

    def _selection_edicai_ai_model(self):
        """Dynamic dropdown options: live Zen list, else cache/static fallback.

        Never raises — Settings must open even when offline. The currently
        saved value is always included so a custom/retired id still displays.
        """
        try:
            ids = self.env['edicai.ai.provider'].get_available_models()
        except Exception:
            _logger.exception('Edicai AI: model selection fallback')
            ids = []
        if not ids:
            ids = list(ZEN_STATIC_MODELS)
        current = self.env['ir.config_parameter'].sudo().get_param('edicai_ai.model')
        if current and current not in ids:
            ids = [current] + ids
        provider = self.env['edicai.ai.provider']
        return [
            (mid, '%s  [%s]' % (mid, provider._model_protocol(mid)))
            for mid in ids
        ]

    def action_edicai_ai_refresh_models(self):
        """Force-refresh the cached Zen model list, then reload Settings."""
        self.ensure_one()
        self.flush_recordset()
        ids = self.env['edicai.ai.provider'].get_available_models(force_refresh=True)
        if not ids:
            raise UserError(_(
                'Could not reach the model list endpoint. '
                'Check the API URL and your network connection.',
            ))
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_edicai_ai_test_connection(self):
        self.ensure_one()
        provider = self.env['edicai.ai.provider']
        # Flush unsaved settings so the test uses the typed values.
        self.flush_recordset()
        try:
            provider.test_connection()
        except UserError:
            raise
        except Exception as exc:
            raise UserError(_('Connection test failed: %s') % exc)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Edicai AI'),
                'message': _('Connection successful! The AI service responded.'),
                'type': 'success',
                'sticky': False,
            },
        }
