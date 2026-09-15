import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class OacisAIController(http.Controller):
    """JSON-RPC endpoints consumed by the OWL chatbot component."""

    # ------------------------------------------------------------------
    # Chat session endpoints
    # ------------------------------------------------------------------

    @http.route('/oacis_ai/chat/sessions', type='json', auth='user')
    def get_sessions(self):
        """Return all chat sessions for the current user."""
        sessions = request.env['oacis.ai.chat.session'].search([
            ('user_id', '=', request.env.user.id),
            ('active', '=', True),
        ], order='write_date desc', limit=50)
        return [
            {
                'id': s.id,
                'title': s.title,
                'write_date': s.write_date.isoformat() if s.write_date else '',
            }
            for s in sessions
        ]

    @http.route('/oacis_ai/chat/prompts', type='json', auth='user')
    def get_prompts(self, category=None):
        """Return shared prompt templates for suggestion chips."""
        domain = [('active', '=', True)]
        if category:
            domain.append(('category', '=', category))
        prompts = request.env['oacis.ai.prompt'].search(domain, limit=20)
        return [
            {'id': p.id, 'name': p.name, 'prompt_text': p.prompt_text,
             'category': p.category}
            for p in prompts
        ]

    @http.route('/oacis_ai/chat/new_session', type='json', auth='user')
    def new_session(self):
        """Create a new chat session and return its id."""
        session = request.env['oacis.ai.chat.session'].create({
            'user_id': request.env.user.id,
        })
        return {'id': session.id, 'title': session.title}

    @http.route('/oacis_ai/chat/messages', type='json', auth='user')
    def get_messages(self, session_id):
        """Return all messages for a given session."""
        messages = request.env['oacis.ai.chat.message'].search([
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

    @http.route('/oacis_ai/chat/send', type='json', auth='user')
    def send_message(self, session_id, message, res_model=None, res_id=None):
        """Send a user message and get an AI reply.

        Persists both the user message and the assistant reply in the
        database, then returns the assistant reply.
        Optionally grounds the answer in an Odoo record (permission-checked).
        """
        session_id = int(session_id)
        env = request.env
        Session = env['oacis.ai.chat.session']
        Message = env['oacis.ai.chat.message']
        provider = env['oacis.ai.provider']

        # Verify ownership
        session = Session.browse(session_id)
        if not session.exists() or session.user_id.id != env.user.id:
            return {'error': 'Session not found.'}
        if not (message or '').strip():
            return {'error': 'Please type a message.'}

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
            reply = provider.chat(history, res_model=res_model, res_id=res_id)
        except Exception as exc:
            _logger.exception('Oacis AI chat error')
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

    @http.route('/oacis_ai/chat/feedback', type='json', auth='user')
    def send_feedback(self, message_id, rating, note=''):
        """Thumbs up/down on an assistant message."""
        msg = request.env['oacis.ai.chat.message'].browse(int(message_id))
        if not msg.exists() or msg.session_id.user_id.id != request.env.user.id:
            return {'error': 'Message not found.'}
        if rating not in ('up', 'down'):
            return {'error': 'Invalid rating.'}
        msg.write({'rating': rating, 'feedback_note': (note or '')[:500]})
        return {'success': True}

    @http.route('/oacis_ai/chat/delete_session', type='json', auth='user')
    def delete_session(self, session_id):
        """Archive (soft-delete) a chat session."""
        session = request.env['oacis.ai.chat.session'].browse(int(session_id))
        if session.exists() and session.user_id.id == request.env.user.id:
            session.write({'active': False})
        return {'success': True}

    # ------------------------------------------------------------------
    # Portal page (students / guardians / faculty with portal access)
    # ------------------------------------------------------------------

    @http.route('/my/ai-assistant', type='http', auth='user')
    def portal_ai_assistant(self, **kwargs):
        """Render the portal chat page. Uses the same JSON APIs."""
        if not request.env.user.has_group('oacis_ai.group_oacis_ai_user'):
            return request.redirect('/my')
        return request.render('oacis_ai.portal_ai_assistant_page', {})
