# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    unicore_ai_api_key = fields.Char(
        string='API Key',
        config_parameter='unicore_ai.api_key',
        help='Your OpenCode Zen API key (or any OpenAI-compatible key).',
    )
    unicore_ai_api_url = fields.Char(
        string='API URL',
        config_parameter='unicore_ai.api_url',
        default='https://opencode.ai/zen/v1/chat/completions',
        help='Endpoint URL for the AI chat completions API.',
    )
    unicore_ai_model = fields.Selection(
        selection=[
            ('deepseek-v4-0324', 'DeepSeek V4 (Default)'),
            ('deepseek-v4-flash-free', 'DeepSeek V4 Flash (Free)'),
            ('gpt-4o', 'GPT-4o'),
            ('gpt-4-mini', 'GPT-4 Mini'),
            ('claude-3.5-sonnet', 'Claude 3.5 Sonnet'),
            ('big-pickle', 'Big Pickle (Free)'),
        ],
        string='Model',
        config_parameter='unicore_ai.model',
        default='deepseek-v4-0324',
        help='AI model identifier.',
    )
    unicore_ai_temperature = fields.Float(
        string='Temperature',
        config_parameter='unicore_ai.temperature',
        default=0.7,
        help='Controls randomness: 0 = deterministic, 1 = very creative.',
    )
    unicore_ai_max_tokens = fields.Integer(
        string='Max Tokens',
        config_parameter='unicore_ai.max_tokens',
        default=2048,
        help='Maximum number of tokens in the AI response.',
    )
