# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class UnicoreAIChatSession(models.Model):
    """Persistent chat session so users can revisit past conversations."""
    _name = 'unicore.ai.chat.session'
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
        'unicore.ai.chat.message',
        'session_id',
        string='Messages',
    )
    active = fields.Boolean(default=True)

    @api.model
    def _auto_title(self, session_id, first_user_message):
        """Set a meaningful title from the first user message."""
        session = self.browse(session_id)
        if session.exists() and session.title == 'New Chat':
            title = first_user_message[:80]
            if len(first_user_message) > 80:
                title += '…'
            session.write({'title': title})


class UnicoreAIChatMessage(models.Model):
    """Individual message inside a chat session."""
    _name = 'unicore.ai.chat.message'
    _description = 'AI Chat Message'
    _order = 'sequence, id'

    session_id = fields.Many2one(
        'unicore.ai.chat.session',
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
