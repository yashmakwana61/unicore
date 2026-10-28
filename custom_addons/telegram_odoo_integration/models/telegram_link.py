"""Bind Telegram chats to students/guardians via one-time passwords (OTP).

Flow
----
1. Portal side (student/guardian logged in as portal user, NO sudo): call
   ``env['telegram.chat.link'].generate_otp(partner)``. It resolves the
   linked ``edicai.student`` / ``edicai.guardian`` record (if those modules are
   installed), stores only a SHA-256 hash of the 6-digit OTP (peppered with a
   server-side secret) with a 10-minute expiry, and returns the plaintext OTP
   **once** for display in the portal.
2. Telegram side: the user sends ``/link <6-digit-code>`` to the bot. The
   dispatcher hook (see ``telegram_link_commands.py``) verifies the OTP,
   binds ``chat_id`` to the partner, mirrors it on
   ``res.partner.telegram_chat_id`` (so the existing ``is_chat_allowed``
   fallback keeps working), and posts audit notes on the partner/student/
   guardian chatter.
3. ``action_unlink`` removes the binding (re-link = unlink + fresh OTP).

Security
--------
* OTPs are never stored in plaintext; only ``sha256(pepper + ':' + otp)``.
* The pepper lives in ``ir.config_parameter``
  (``telegram_odoo_integration.otp_pepper``) and is auto-generated once via
  ``secrets.token_hex``. Comparison uses ``hmac.compare_digest``.
* 10-minute expiry, max 5 failed attempts per chat then a 30-minute lockout.
* Portal issuance runs with the user's own rights (no ``sudo()`` on user
  data); the webhook path uses ``sudo()`` narrowly on this technical model
  only, since the OTP itself is the proof of authorization.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

CONFIG_OTP_PEPPER = 'telegram_odoo_integration.otp_pepper'

OTP_TTL_MINUTES = 10
MAX_OTP_ATTEMPTS = 5
LOCKOUT_MINUTES = 30


class TelegramChatLink(models.Model):
    _name = 'telegram.chat.link'
    _description = 'Telegram Chat Link (student/guardian binding)'
    _rec_name = 'chat_id'
    _order = 'id desc'

    chat_id = fields.Char(string='Telegram Chat ID', index=True)
    telegram_username = fields.Char(string='Telegram Username', index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Contact', index=True, ondelete='cascade')
    student_id = fields.Many2one(
        'edicai.student', string='Student', index=True, ondelete='set null')
    guardian_id = fields.Many2one(
        'edicai.guardian', string='Guardian', index=True, ondelete='set null')
    otp_hash = fields.Char(
        string='OTP Hash', copy=False,
        help='SHA-256 of pepper + OTP. Plaintext OTP is never stored.')
    otp_expiry = fields.Datetime(string='OTP Expires At', copy=False)
    otp_attempts = fields.Integer(string='Failed OTP Attempts', default=0)
    locked_until = fields.Datetime(string='Locked Until', copy=False)
    verified = fields.Boolean(string='Verified', default=False, index=True)
    company_id = fields.Many2one(
        'res.company', string='Institution',
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('unique_chat_id', 'UNIQUE(chat_id)',
         'This Telegram chat is already linked.'),
    ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_pepper(self):
        """Return the server-side OTP pepper, generating it once if missing."""
        ICP = self.env['ir.config_parameter'].sudo()
        pepper = ICP.get_param(CONFIG_OTP_PEPPER, '')
        if not pepper:
            pepper = secrets.token_hex(32)
            ICP.set_param(CONFIG_OTP_PEPPER, pepper)
            _logger.info('Generated Telegram OTP pepper')
        return pepper

    @staticmethod
    def _hash_otp(otp, pepper):
        return hashlib.sha256(
            ('%s:%s' % (pepper, otp)).encode('utf-8')).hexdigest()

    def _resolve_profile_refs(self, partner):
        """Return (student, guardian) records for ``partner`` or (None, None).

        The edicai modules are optional; missing models are tolerated so this
        module never hard-depends on them.
        """
        student = guardian = None
        for model, field in (('edicai.student', 'student_id'),
                             ('edicai.guardian', 'guardian_id')):
            try:
                Model = self.env[model]
            except KeyError:
                continue
            try:
                rec = Model.search([('partner_id', '=', partner.id)], limit=1)
            except Exception:
                continue
            if rec:
                if field == 'student_id':
                    student = rec
                else:
                    guardian = rec
        return student, guardian

    def _audit(self, body):
        """Post ``body`` on partner/student/guardian chatter (best effort)."""
        for rec in (self.partner_id, self.student_id, self.guardian_id):
            try:
                if rec and hasattr(rec, 'message_post'):
                    rec.message_post(body=body)
            except Exception:
                _logger.exception('Failed to post link audit note')

    # ------------------------------------------------------------------
    # Portal-side issuance (called WITHOUT sudo as the portal user)
    # ------------------------------------------------------------------
    def generate_otp(self, partner):
        """Issue a fresh 6-digit OTP for ``partner``; return it (plaintext).

        Creates/updates the pending (unverified) link row for this partner.
        Any previous OTP is invalidated and the attempt counter reset.
        """
        if not partner or not partner.id:
            raise ValidationError('A contact is required to issue an OTP.')
        student, guardian = self._resolve_profile_refs(partner)
        otp = '%06d' % (secrets.randbelow(900000) + 100000)
        pepper = self._get_pepper()
        expiry = fields.Datetime.now() + timedelta(minutes=OTP_TTL_MINUTES)
        company = partner.company_id if partner.company_id else (
            (student.company_id if student and student.company_id else False)
            or (guardian.company_id
                if guardian and hasattr(guardian, 'company_id')
                and guardian.company_id else False)
            or self.env.company)
        link = self.search([('partner_id', '=', partner.id)], limit=1)
        vals = {
            'partner_id': partner.id,
            'student_id': student.id if student else False,
            'guardian_id': guardian.id if guardian else False,
            'otp_hash': self._hash_otp(otp, pepper),
            'otp_expiry': expiry,
            'otp_attempts': 0,
            'locked_until': False,
            'verified': False,
            'company_id': company.id if company else False,
        }
        if link:
            link.write(vals)
        else:
            link = self.create(vals)
        link._audit('Telegram linking OTP issued (expires %s).' % expiry)
        return otp

    # ------------------------------------------------------------------
    # Bot-side verification (webhook runs as public; sudo on THIS model)
    # ------------------------------------------------------------------
    def verify_otp(self, chat_id, otp, telegram_username=None):
        """Verify ``otp`` for ``chat_id``; bind on success.

        :return: (link_record, error_message). Exactly one is set.
        """
        Link = self.sudo()
        chat_id = str(chat_id or '').strip()
        otp = str(otp or '').strip()
        if not chat_id or len(otp) != 6 or not otp.isdigit():
            return None, 'Invalid code format.'
        now = fields.Datetime.now()
        pepper = self._get_pepper()

        chat_link = Link.search([('chat_id', '=', chat_id)], limit=1)
        if chat_link.locked_until and chat_link.locked_until > now:
            return None, 'locked'

        digest = self._hash_otp(otp, pepper)
        now_s = fields.Datetime.to_string(now)
        pending = Link.search([
            ('otp_hash', '!=', False),
            ('otp_expiry', '>', now_s),
            '|', ('locked_until', '=', False),
            ('locked_until', '<=', now_s),
        ], limit=200)
        # NOTE: expired/locked rows are excluded above; also reject rows
        # locked in the past window that still carry attempts>=MAX below.
        match = None
        for cand in pending:
            if cand.locked_until and cand.locked_until > now:
                continue
            if cand.otp_attempts >= MAX_OTP_ATTEMPTS:
                continue
            if hmac.compare_digest(cand.otp_hash or '', digest):
                match = cand
                break

        if not match:
            # Attribute the failure to this chat for lockout purposes.
            target = chat_link
            if not target:
                target = Link.create({'chat_id': chat_id,
                                      'telegram_username': telegram_username,
                                      'otp_attempts': 0})
            attempts = (target.otp_attempts or 0) + 1
            vals = {'otp_attempts': attempts}
            if attempts >= MAX_OTP_ATTEMPTS:
                vals['locked_until'] = now + timedelta(minutes=LOCKOUT_MINUTES)
            target.write(vals)
            if vals.get('locked_until'):
                target._audit(
                    'Telegram chat %s locked after %d bad OTP attempts.'
                    % (chat_id, attempts))
                return None, 'locked'
            return None, 'Invalid or expired code.'

        # Conflict: this partner is already verified on a different chat.
        if match.verified and match.chat_id and match.chat_id != chat_id:
            return None, ('This code was already used on another device. '
                           'Unlink it first with /unlink, then link here.')

        # Conflict: this chat is bound to a different partner.
        if chat_link and chat_link.id != match.id and chat_link.verified \
                and chat_link.partner_id and match.partner_id \
                and chat_link.partner_id.id != match.partner_id.id:
            return None, ('This Telegram account is already linked. '
                           'Send /unlink first, then /link <code>.')

        # Bind: reuse the chat row if it is the pending/unverified placeholder.
        if chat_link and chat_link.id != match.id and not chat_link.verified \
                and not chat_link.partner_id:
            chat_link.unlink()
            chat_link = None
        match.write({
            'chat_id': chat_id,
            'telegram_username': telegram_username,
            'verified': True,
            'otp_hash': False,
            'otp_expiry': False,
            'otp_attempts': 0,
            'locked_until': False,
        })
        # Mirror on the partner so existing allow-list fallback keeps working.
        if match.partner_id:
            try:
                match.partner_id.sudo().write({'telegram_chat_id': chat_id})
            except Exception:
                _logger.exception('Could not mirror telegram_chat_id')
        match._audit('Telegram chat %s linked and verified.' % chat_id)
        _logger.info('Telegram chat %s linked to partner %s',
                     chat_id, match.partner_id.id if match.partner_id else '-')
        return match, None

    def action_unlink(self):
        """Remove the chat binding (user-data safe: keeps partner/student)."""
        for link in self:
            chat = link.chat_id
            partner = link.partner_id
            link._audit('Telegram chat %s unlinked.' % (chat or '-'))
            if partner and partner.telegram_chat_id == chat:
                try:
                    partner.sudo().write({'telegram_chat_id': False})
                except Exception:
                    _logger.exception('Could not clear telegram_chat_id')
            link.write({'verified': False, 'chat_id': False,
                        'otp_hash': False, 'otp_expiry': False,
                        'otp_attempts': 0, 'locked_until': False,
                        'telegram_username': False})
        return True

    @api.autovacuum
    def _autovacuum_expired_otps(self):
        """Scrub stale OTP hashes from unverified rows (runs daily)."""
        stale = self.sudo().search([
            ('verified', '=', False),
            ('otp_hash', '!=', False),
            ('otp_expiry', '<', fields.Datetime.now()),
        ])
        if stale:
            stale.write({'otp_hash': False, 'otp_expiry': False})
            _logger.info('Scrubbed %d expired Telegram OTP hashes', len(stale))
        # Table-bloat guard: failed guesses from unknown chats create
        # unverified partner-less placeholder rows for lockout tracking;
        # purge ones older than 24h so they cannot accumulate forever.
        cutoff = fields.Datetime.to_string(
            fields.Datetime.now() - timedelta(hours=24))
        junk = self.sudo().search([
            ('verified', '=', False),
            ('partner_id', '=', False),
            ('otp_hash', '=', False),
            ('create_date', '<', cutoff),
        ])
        if junk:
            junk.unlink()
            _logger.info('Purged %d stale Telegram link placeholders', len(junk))
