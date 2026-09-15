"""Business logic for the Telegram -> Sales Order integration.

The service is a plain Python class (no ORM model) so it is easy to unit
test and does not pollute the Odoo model registry. It receives an ``env``
and performs all writes with explicitly scoped ``sudo()`` calls because it
runs in the context of the public webhook route.

Session-based flow:
  /neworder  → start a new order session
  /done      → submit collected messages + attachments to AI Parser
  /cancel    → discard current session
  /status    → show current session status
  <text>     → add text to active session
  <files>    → add files to active session
"""
import hashlib
import logging
import os
import tempfile
import uuid

import requests

_logger = logging.getLogger(__name__)

CONFIG_BOT_TOKEN = 'telegram_odoo_integration.bot_token'
CONFIG_ALLOWED_CHAT_ID = 'telegram_odoo_integration.allowed_chat_id'
CONFIG_MAX_FILE_SIZE_MB = 'telegram_odoo_integration.max_file_size_mb'

DEFAULT_MAX_FILE_SIZE_MB = 10

ALLOWED_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
}

COMMANDS = {
    '/neworder': 'new_order',
    '/done': 'submit_order',
    '/cancel': 'cancel_order',
    '/status': 'show_status',
    '/start': 'show_help',
    '/help': 'show_help',
}


class TelegramBotService:
    """Coordinates incoming Telegram updates and session-based order flow."""

    def __init__(self, env):
        self.env = env

    # ------------------------------------------------------------------ #
    # Configuration helpers
    # ------------------------------------------------------------------ #
    def get_bot_token(self):
        """Resolve the bot token.

        Precedence: ``TELEGRAM_BOT_TOKEN`` environment variable first,
        so production deployments can avoid storing the secret in
        the database.
        """
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        if not token:
            token = self.env['ir.config_parameter'].sudo().get_param(
                CONFIG_BOT_TOKEN, '')
        return token.strip()

    def get_allowed_chat_id(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            CONFIG_ALLOWED_CHAT_ID, '').strip()

    def is_chat_allowed(self, chat_id):
        """Return True only for the configured chat id.

        If no chat id is configured, no one is allowed (fail-closed).
        """
        allowed = self.get_allowed_chat_id()
        if not allowed:
            _logger.warning(
                'No allowed chat id configured in %s; rejecting all chats',
                CONFIG_ALLOWED_CHAT_ID)
            return False
        return str(chat_id or '') == str(allowed).strip()

    def get_max_file_size_bytes(self):
        mb = int(self.env['ir.config_parameter'].sudo().get_param(
            CONFIG_MAX_FILE_SIZE_MB, str(DEFAULT_MAX_FILE_SIZE_MB)))
        return mb * 1024 * 1024

    # ------------------------------------------------------------------ #
    # Idempotency
    # ------------------------------------------------------------------ #
    def _is_duplicate_update(self, update_id):
        """Check if this update has already been processed."""
        if not update_id:
            return False
        existing = self.env['telegram.message'].sudo().search([
            ('update_id', '=', str(update_id)),
        ], limit=1)
        return bool(existing)

    # ------------------------------------------------------------------ #
    # Staff resolution
    # ------------------------------------------------------------------ #
    def _resolve_staff(self, chat_id, username, from_user_id):
        """Map a Telegram user to an Odoo internal user (res.users).

        Looks for a partner with matching telegram_chat_id or
        telegram_username, then finds the linked internal user.
        If no internal user is found, returns the public user.
        """
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([
            '|',
            ('telegram_chat_id', '=', str(chat_id)),
            ('telegram_username', '=', username),
        ], limit=1)

        if partner and partner.user_ids:
            return partner.user_ids[0]

        # Fall back to public user (unauthenticated)
        return self.env.ref('base.public_user')

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def process_update(self, data):
        """Handle one Telegram update dict.

        :return: JSON-serialisable dict for the webhook response.
        """
        data = dict(data or {})
        if 'params' in data and not data.get('update_id'):
            data = dict(data.get('params') or {})

        update_id = data.get('update_id')
        message = data.get('message') or data.get('edited_message') or {}
        document = message.get('document') or {}
        photo = message.get('photo') or []
        chat = message.get('chat') or {}
        chat_id = str(chat.get('id') or '')
        from_user = message.get('from') or {}
        username = (
            from_user.get('username')
            or from_user.get('first_name')
            or str(from_user.get('id') or '')
        )
        from_user_id = from_user.get('id')
        text = message.get('text') or ''
        telegram_msg_id = str(message.get('message_id') or '')

        # 1. Idempotency: reject duplicate updates.
        if self._is_duplicate_update(update_id):
            _logger.info('Duplicate update %s, skipping', update_id)
            return {'success': True, 'duplicate': True}

        # 2. Audit: persist every raw update regardless of outcome.
        log = self.env['telegram.message'].sudo()._log_update(data)

        # 3. Security: only allow the configured chat id.
        if not self.is_chat_allowed(chat_id):
            _logger.warning(
                'Rejected Telegram update %s from unauthorized chat %s',
                update_id, chat_id)
            log.write({
                'state': 'rejected',
                'error_message': 'Unauthorized chat id',
            })
            self.send_telegram_message(
                chat_id,
                'You are not authorized to place orders through this bot.')
            return {'success': False, 'error': 'Unauthorized chat id'}

        # 4. Resolve staff member.
        staff = self._resolve_staff(chat_id, username, from_user_id)

        # 5. Handle file attachments (photos or documents).
        has_files = bool(photo or document)
        if has_files:
            return self._handle_file_message(
                log, chat_id, username, staff, photo, document,
                telegram_msg_id, text)

        # 6. Handle text messages.
        if not text:
            log.write({'state': 'ignored'})
            return {'success': False, 'error': 'No content', 'ignored': True}

        return self._handle_text_message(
            log, chat_id, username, staff, text, telegram_msg_id)

    # ------------------------------------------------------------------ #
    # Text message handling
    # ------------------------------------------------------------------ #
    def _handle_text_message(self, log, chat_id, username, staff,
                             text, telegram_msg_id):
        """Route a text message to the appropriate handler."""
        text_stripped = text.strip()
        command = text_stripped.lower().split()[0] if text_stripped else ''

        if command in COMMANDS:
            handler_name = COMMANDS[command]
            handler = getattr(self, '_cmd_%s' % handler_name, None)
            if handler:
                return handler(
                    log, chat_id, username, staff, text_stripped)

        # Not a command — add to active session or show help.
        return self._add_text_to_session(
            log, chat_id, username, staff, text_stripped, telegram_msg_id)

    def _cmd_show_help(self, log, chat_id, username, staff, text):
        """Show help message."""
        log.write({'state': 'ignored'})
        help_text = (
            'Welcome! To place an order:\n\n'
            '1. Send /neworder to start a new order\n'
            '2. Send text messages with order details\n'
            '3. Send images, PDFs, or Excel files as needed\n'
            '4. Send /done when ready to submit\n\n'
            'Other commands:\n'
            '/status - Check current order status\n'
            '/cancel - Cancel current order'
        )
        self.send_telegram_message(chat_id, help_text)
        return {'success': True, 'message': 'help sent', 'ignored': True}

    def _cmd_new_order(self, log, chat_id, username, staff, text):
        """Start a new order session."""
        # Check for existing active session.
        active = self._get_active_session(chat_id)
        if active:
            log.write({'state': 'ignored'})
            self.send_telegram_message(
                chat_id,
                'You already have an active order session (%s).\n'
                'Send /done to submit it, /cancel to discard it, '
                'or continue sending messages.'
                % active.session_id[:8])
            return {
                'success': True,
                'message': 'active session exists',
                'session_id': active.session_id,
            }

        session = self.env['telegram.order.session'].sudo().create({
            'staff_id': staff.id,
            'chat_id': chat_id,
            'telegram_username': username,
            'state': 'collecting',
            'last_update_id': str(log.update_id),
        })
        log.write({
            'state': 'received',
            'session_id': session.id,
        })

        _logger.info(
            'New order session %s started by %s', session.session_id, username)
        self.send_telegram_message(
            chat_id,
            'New order started.\n'
            'Send customer details and order information.\n'
            'Send /done when ready to submit.')
        return {
            'success': True,
            'message': 'session started',
            'session_id': session.session_id,
        }

    def _cmd_submit_order(self, log, chat_id, username, staff, text):
        """Submit the active session to the AI Parser."""
        session = self._get_active_session(chat_id)
        if not session:
            log.write({'state': 'ignored'})
            self.send_telegram_message(
                chat_id,
                'No active order session. Send /neworder to start one.')
            return {'success': False, 'error': 'No active session'}

        if not session.message_ids and not session.attachment_ids:
            self.send_telegram_message(
                chat_id,
                'No messages or files collected yet.\n'
                'Send your order details first, then /done.')
            return {'success': False, 'error': 'Empty session'}

        log.write({'session_id': session.id})
        self.send_telegram_message(chat_id, 'Submitting your order...')

        session.action_submit()

        status_msg = session.get_status_message()
        self.send_telegram_message(chat_id, status_msg)
        return {
            'success': True,
            'message': status_msg,
            'session_id': session.session_id,
            'state': session.state,
        }

    def _cmd_cancel_order(self, log, chat_id, username, staff, text):
        """Cancel the active session."""
        session = self._get_active_session(chat_id)
        if not session:
            log.write({'state': 'ignored'})
            self.send_telegram_message(
                chat_id, 'No active order session to cancel.')
            return {'success': False, 'error': 'No active session'}

        session.action_cancel()
        log.write({'session_id': session.id})
        self.send_telegram_message(chat_id, 'Order cancelled.')
        return {
            'success': True,
            'message': 'cancelled',
            'session_id': session.session_id,
        }

    def _cmd_show_status(self, log, chat_id, username, staff, text):
        """Show status of the active session."""
        session = self._get_active_session(chat_id)
        if not session:
            log.write({'state': 'ignored'})
            self.send_telegram_message(
                chat_id, 'No active order session.')
            return {'success': True, 'message': 'no session'}

        log.write({'session_id': session.id})
        status_msg = session.get_status_message()
        self.send_telegram_message(chat_id, status_msg)
        return {
            'success': True,
            'message': status_msg,
            'session_id': session.session_id,
            'state': session.state,
        }

    # ------------------------------------------------------------------ #
    # Text to session
    # ------------------------------------------------------------------ #
    def _add_text_to_session(self, log, chat_id, username, staff,
                             text, telegram_msg_id):
        """Add a text message to the active session."""
        session = self._get_active_session(chat_id)
        if not session:
            log.write({'state': 'ignored'})
            self.send_telegram_message(
                chat_id,
                'No active order session. Send /neworder to start one.')
            return {'success': False, 'error': 'No active session'}

        sequence = len(session.message_ids) + 1
        self.env['telegram.session.message'].sudo().create({
            'session_id': session.id,
            'message_text': text,
            'telegram_message_id': telegram_msg_id,
            'sequence': sequence,
        })
        session.write({'last_update_id': str(log.update_id)})
        log.write({'session_id': session.id, 'state': 'received'})

        _logger.info(
            'Text added to session %s (seq %d)',
            session.session_id, sequence)
        return {
            'success': True,
            'message': 'text added',
            'session_id': session.session_id,
        }

    # ------------------------------------------------------------------ #
    # File handling
    # ------------------------------------------------------------------ #
    def _handle_file_message(self, log, chat_id, username, staff,
                             photo, document, telegram_msg_id, caption):
        """Handle a file attachment (photo or document)."""
        session = self._get_active_session(chat_id)
        if not session:
            log.write({'state': 'ignored'})
            self.send_telegram_message(
                chat_id,
                'Received a file, but no active order session.\n'
                'Send /neworder to start one first.')
            return {'success': False, 'error': 'No active session for file'}

        # Determine file info from Telegram.
        if photo:
            # Photos are sent as multiple sizes; use the largest.
            file_info = photo[-1]
            file_id = file_info.get('file_id', '')
            file_unique_id = file_info.get('file_unique_id', '')
            filename = 'photo_%s.jpg' % file_unique_id
            mime_type = 'image/jpeg'
            file_size = file_info.get('file_size', 0)
        elif document:
            file_info = document
            file_id = document.get('file_id', '')
            file_unique_id = document.get('file_unique_id', '')
            filename = document.get('file_name', 'attachment')
            mime_type = document.get('mime_type', 'application/octet-stream')
            file_size = document.get('file_size', 0)
        else:
            log.write({'state': 'ignored'})
            return {'success': False, 'error': 'No file found'}

        # Validate MIME type.
        if mime_type not in ALLOWED_MIME_TYPES:
            self.send_telegram_message(
                chat_id,
                'File type "%s" is not supported.\n'
                'Allowed: JPEG, PNG, WebP, PDF, Excel (.xlsx, .xls).'
                % mime_type)
            log.write({'state': 'error', 'error_message': 'Unsupported MIME'})
            return {'success': False, 'error': 'Unsupported MIME type'}

        # Validate file size.
        max_size = self.get_max_file_size_bytes()
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            self.send_telegram_message(
                chat_id,
                'File is too large (%.1f MB). Maximum allowed: %d MB.'
                % (file_size / (1024 * 1024), max_mb))
            log.write({'state': 'error', 'error_message': 'File too large'})
            return {'success': False, 'error': 'File too large'}

        # Download and store the file.
        try:
            file_path, file_hash = self._download_telegram_file(
                file_id, filename)
        except Exception as exc:
            _logger.exception('Failed to download file from Telegram')
            self.send_telegram_message(
                chat_id, 'Failed to download the file. Please try again.')
            log.write({'state': 'error', 'error_message': str(exc)})
            return {'success': False, 'error': str(exc)}

        # Add caption as text message if present.
        if caption:
            seq_text = len(session.message_ids) + 1
            self.env['telegram.session.message'].sudo().create({
                'session_id': session.id,
                'message_text': caption,
                'telegram_message_id': telegram_msg_id,
                'sequence': seq_text,
            })

        # Create attachment record.
        seq_att = len(session.attachment_ids) + 1
        self.env['telegram.session.attachment'].sudo().create({
            'session_id': session.id,
            'filename': filename,
            'mime_type': mime_type,
            'file_size': file_size,
            'file_hash': file_hash,
            'file_path': file_path,
            'telegram_file_id': file_id,
            'telegram_file_unique_id': file_unique_id,
            'sequence': seq_att,
        })

        session.write({'last_update_id': str(log.update_id)})
        log.write({'session_id': session.id, 'state': 'received'})

        _logger.info(
            'File %s added to session %s', filename, session.session_id)
        return {
            'success': True,
            'message': 'file added',
            'session_id': session.session_id,
            'filename': filename,
        }

    def _download_telegram_file(self, telegram_file_id, original_filename):
        """Download a file from Telegram and store it securely.

        :return: tuple (file_path, sha256_hash)
        """
        token = self.get_bot_token()
        if not token:
            raise ValueError('Telegram bot token not configured')

        # Step 1: Get file path from Telegram API.
        get_file_url = 'https://api.telegram.org/bot%s/getFile' % token
        resp = requests.get(
            get_file_url,
            params={'file_id': telegram_file_id},
            timeout=30,
        )
        resp.raise_for_status()
        file_data = resp.json()
        if not file_data.get('ok'):
            raise ValueError(
                'Telegram getFile failed: %s' % file_data.get('description'))

        file_path_telegram = file_data['result']['file_path']

        # Step 2: Download the file.
        download_url = (
            'https://api.telegram.org/bot%s/files/%s'
            % (token, file_path_telegram))
        file_resp = requests.get(download_url, timeout=60)
        file_resp.raise_for_status()

        # Step 3: Store securely with random filename.
        ext = os.path.splitext(original_filename)[1] or '.bin'
        secure_name = '%s%s' % (uuid.uuid4().hex, ext)
        temp_dir = tempfile.mkdtemp(prefix='tg_attachments_')
        file_path = os.path.join(temp_dir, secure_name)

        with open(file_path, 'wb') as fh:
            fh.write(file_resp.content)

        # Step 4: Compute hash.
        sha256 = hashlib.sha256(file_resp.content).hexdigest()

        return file_path, 'sha256:%s' % sha256

    # ------------------------------------------------------------------ #
    # Session lookup
    # ------------------------------------------------------------------ #
    def _get_active_session(self, chat_id):
        """Return the most recent active session for this chat, or None."""
        Session = self.env['telegram.order.session'].sudo()
        session = Session.search([
            ('chat_id', '=', str(chat_id)),
            ('state', 'in', ('new', 'collecting')),
        ], order='id desc', limit=1)
        return session if session else None

    # ------------------------------------------------------------------ #
    # Telegram Bot API
    # ------------------------------------------------------------------ #
    def send_telegram_message(self, chat_id, text):
        """Send a reply to ``chat_id`` through the Telegram Bot API.

        :return: parsed JSON response dict or ``None`` on failure.
        """
        token = self.get_bot_token()
        if not token:
            _logger.error(
                'Telegram bot token not configured (%s); cannot send reply',
                CONFIG_BOT_TOKEN)
            return None
        if not chat_id:
            _logger.warning('No chat id available to send Telegram reply')
            return None

        url = 'https://api.telegram.org/bot%s/sendMessage' % token
        try:
            response = requests.post(
                url,
                json={'chat_id': chat_id, 'text': text},
                timeout=10,
            )
            response.raise_for_status()
            _logger.debug('Telegram reply sent to chat %s: %s', chat_id, text)
            return response.json()
        except requests.RequestException as exc:
            _logger.error('Failed to send Telegram reply to chat %s: %s',
                          chat_id, exc)
            return None
