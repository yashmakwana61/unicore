"""Bot-side /link and /unlink command handling (OTP chat binding).

This module is deliberately decoupled from the order dispatcher: the ONLY
touch point in ``telegram_bot_service.py`` is a 4-line hook at the top of
``process_update`` (before the allow-list gate, so unknown chats CAN link)::

    from odoo.addons.telegram_odoo_integration.models import telegram_link_commands as _lc
    _link_res = _lc.try_handle_link_command(self, log, chat_id, username, text)
    if _link_res is not None:
        return _link_res

``try_handle_link_command`` returns ``None`` for every non-link message so the
normal order flow is untouched. It never raises: all failures are converted
into user-facing replies. The OTP is the authorization, so this path must run
BEFORE ``is_chat_allowed`` rejects the unknown chat.
"""
import logging

_logger = logging.getLogger(__name__)

LINK_COMMANDS = ('/link', '/unlink')


def _base_command(text):
    first = (text or '').strip().split()[0].lower() if (text or '').strip() else ''
    return first.split('@')[0]


def try_handle_link_command(service, log, chat_id, username, text):
    """Handle ``/link <otp>`` / ``/unlink``; return result dict or ``None``."""
    try:
        return _handle(service, log, chat_id, username, text)
    except Exception:
        _logger.exception('Link command handler failed')
        return None


def _handle(service, log, chat_id, username, text):
    cmd = _base_command(text)
    if cmd not in LINK_COMMANDS:
        return None
    env = service.env
    Link = env['telegram.chat.link']
    if cmd == '/unlink':
        return _do_unlink(service, log, Link, chat_id)
    parts = (text or '').strip().split()
    if len(parts) < 2:
        service.send_telegram_message(
            chat_id,
            'To link your account, get a 6-digit code from your student / '
            'guardian portal and send:\n/link 123456')
        try:
            log.write({'state': 'ignored'})
        except Exception:
            pass
        return {'success': False, 'error': 'Missing OTP', 'ignored': True}
    otp = parts[1].strip()
    link, error = Link.verify_otp(chat_id, otp, telegram_username=username)
    if link:
        try:
            log.write({'state': 'ignored'})
        except Exception:
            pass
        who = link.partner_id.display_name if link.partner_id else 'your account'
        service.send_telegram_message(
            chat_id,
            '\u2705 Linked! This Telegram account is now connected to %s.\n'
            'Send /unlink any time to disconnect.' % who)
        return {'success': True, 'message': 'chat linked',
                'link_id': link.id, 'ignored': True}
    if error == 'locked':
        msg = ('\u26a0\ufe0f Too many wrong codes. Linking is locked for '
               '30 minutes. Please try again later or request a new code.')
    else:
        msg = ('\u274c %s\nRequest a fresh code from the portal and send '
               '/link <6-digit-code>.' % (error or 'Invalid code.'))
    try:
        log.write({'state': 'ignored'})
    except Exception:
        pass
    service.send_telegram_message(chat_id, msg)
    return {'success': False, 'error': error or 'Invalid OTP', 'ignored': True}


def _do_unlink(service, log, Link, chat_id):
    link = Link.sudo().search([
        ('chat_id', '=', str(chat_id)), ('verified', '=', True),
    ], limit=1)
    try:
        log.write({'state': 'ignored'})
    except Exception:
        pass
    if not link:
        service.send_telegram_message(
            chat_id, 'This Telegram account is not linked to any profile.')
        return {'success': True, 'message': 'not linked', 'ignored': True}
    link.action_unlink()
    service.send_telegram_message(
        chat_id,
        'Disconnected. To link again, get a new code from the portal and '
        'send /link <6-digit-code>.')
    return {'success': True, 'message': 'chat unlinked', 'ignored': True}
