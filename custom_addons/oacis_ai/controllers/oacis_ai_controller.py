import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class UnicoreAIController(http.Controller):
    """JSON-RPC endpoints consumed by the OWL chatbot component."""

    # ------------------------------------------------------------------
    # Chat session endpoints
    # ------------------------------------------------------------------

    @http.route('/unicore_ai/chat/sessions', type='json', auth='user')
    def get_sessions(self):
        """Return all chat sessions for the current user."""
        sessions = request.env['unicore.ai.chat.session'].search([
            ('user_id', '=', request.env.user.id),
        ], order='write_date desc', limit=50)
        return [
            {
                'id': s.id,
                'title': s.title,
                'write_date': s.write_date.isoformat() if s.write_date else '',
            }
            for s in sessions
        ]

    @http.route('/unicore_ai/chat/new_session', type='json', auth='user')
    def new_session(self):
        """Create a new chat session and return its id."""
        session = request.env['unicore.ai.chat.session'].create({
            'user_id': request.env.user.id,
        })
        return {'id': session.id, 'title': session.title}

    @http.route('/unicore_ai/chat/messages', type='json', auth='user')
    def get_messages(self, session_id):
        """Return all messages for a given session."""
        messages = request.env['unicore.ai.chat.message'].search([
            ('session_id', '=', int(session_id)),
            ('session_id.user_id', '=', request.env.user.id),
        ], order='sequence, id')
        return [
            {
                'id': m.id,
                'role': m.role,
                'content': m.content,
            }
            for m in messages
        ]

    @http.route('/unicore_ai/chat/send', type='json', auth='user')
    def send_message(self, session_id, message):
        """Send a user message and get an AI reply.

        Persists both the user message and the assistant reply in the
        database, then returns the assistant reply.
        """
        session_id = int(session_id)
        env = request.env
        Session = env['unicore.ai.chat.session']
        Message = env['unicore.ai.chat.message']
        provider = env['unicore.ai.provider']

        # Verify ownership
        session = Session.browse(session_id)
        if not session.exists() or session.user_id.id != env.user.id:
            return {'error': 'Session not found.'}

        # Determine next sequence
        last_seq = 0
        if session.message_ids:
            last_seq = max(session.message_ids.mapped('sequence'))

        # Persist user message
        Message.create({
            'session_id': session_id,
            'role': 'user',
            'content': message,
            'sequence': last_seq + 10,
        })

        # Auto-title on first message
        if len(session.message_ids) <= 1:
            Session._auto_title(session_id, message)

        # Build conversation history for the API
        history = [
            {'role': m.role, 'content': m.content}
            for m in session.message_ids.sorted('sequence')
        ]

        try:
            reply = provider.chat(history)
        except Exception as exc:
            _logger.exception('Unicore AI chat error')
            reply = f'⚠️ Sorry, I encountered an error: {exc}'

        # Persist assistant reply
        Message.create({
            'session_id': session_id,
            'role': 'assistant',
            'content': reply,
            'sequence': last_seq + 20,
        })

        return {
            'reply': reply,
            'session_title': session.title,
        }

    @http.route('/unicore_ai/chat/delete_session', type='json', auth='user')
    def delete_session(self, session_id):
        """Archive (soft-delete) a chat session."""
        session = request.env['unicore.ai.chat.session'].browse(int(session_id))
        if session.exists() and session.user_id.id == request.env.user.id:
            session.write({'active': False})
        return {'success': True}
