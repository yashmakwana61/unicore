import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class OacisAIChatSession(models.Model):
    """Persistent chat session so users can revisit past conversations."""
    _name = 'oacis.ai.chat.session'
    _description = 'AI Chat Session'
    _order = 'write_date desc'
    _rec_name = 'title'

    title = fields.Char(
        string='Title',
        default='New Chat',
        required=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        required=True,
        ondelete='cascade',
        index=True,
    )
    message_ids = fields.One2many(
        'oacis.ai.chat.message',
        'session_id',
        string='Messages',
    )
    active = fields.Boolean(default=True)
    message_count = fields.Integer(
        string='Messages',
        compute='_compute_message_count',
    )

    @api.depends('message_ids')
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)

    @api.model
    def _auto_title(self, session_id, first_user_message):
        """Set a meaningful title from the first user message."""
        session = self.browse(session_id)
        if session.exists() and session.title == 'New Chat':
            title = first_user_message[:80]
            if len(first_user_message) > 80:
                title += '…'
            session.write({'title': title})


class OacisAIChatMessage(models.Model):
    """Individual message inside a chat session."""
    _name = 'oacis.ai.chat.message'
    _description = 'AI Chat Message'
    _order = 'sequence, id'

    session_id = fields.Many2one(
        'oacis.ai.chat.session',
        string='Session',
        required=True,
        ondelete='cascade',
        index=True,
    )
    role = fields.Selection(
        selection=[
            ('user', 'User'),
            ('assistant', 'Assistant'),
        ],
        string='Role',
        required=True,
    )
    content = fields.Text(
        string='Content',
        required=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    # --- Usefulness loop ---
    rating = fields.Selection(
        selection=[('up', '👍 Helpful'), ('down', '👎 Not helpful')],
        string='Rating',
    )
    feedback_note = fields.Char(string='Feedback Note')
    tokens_estimate = fields.Integer(
        string='Tokens (est.)',
        help='Rough estimate (chars / 4) for cost awareness.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            content = vals.get('content') or ''
            if not vals.get('tokens_estimate') and content:
                vals['tokens_estimate'] = max(1, len(content) // 4)
        return super().create(vals_list)
