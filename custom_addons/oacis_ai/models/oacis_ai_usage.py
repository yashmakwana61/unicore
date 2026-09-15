from odoo import fields, models


class OacisAIUsageLog(models.Model):
    """Append-only log of AI calls for cost awareness & governance."""
    _name = 'oacis.ai.usage.log'
    _description = 'AI Usage Log'
    _order = 'create_date desc'

    user_id = fields.Many2one(
        'res.users', string='User', required=True,
        default=lambda self: self.env.user, ondelete='cascade', index=True,
    )
    model_used = fields.Char(string='Model')
    feature = fields.Char(
        string='Feature',
        help='e.g. chatbot, wizard:generate, quiz, notice, record_summary',
    )
    tokens_estimate = fields.Integer(string='Tokens (est.)')
    latency_ms = fields.Integer(string='Latency (ms)')
    success = fields.Boolean(string='Success', default=True)
    error_message = fields.Char(string='Error')
