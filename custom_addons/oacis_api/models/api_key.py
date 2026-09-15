import hashlib
import secrets
import time
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import AccessDenied


class ApiKeyQuotaExceeded(Exception):
    """Raised when an API key exhausts its daily call limit.

    Distinct from AccessDenied so controllers can answer HTTP 429
    (with Retry-After) instead of masking the condition as a bad
    credential (401).
    """


class OacisApiKey(models.Model):
    _name = 'oacis.api.key'
    _description = 'API Key'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Key Name',
        required=True,
        tracking=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    # Only a SHA-256 fingerprint is persisted; the full secret is
    # shown exactly once via oacis.api.key.token.wizard right after
    # generation and validated afterwards through its hash.
    token_hash = fields.Char(
        string='Key Hash',
        readonly=True,
        copy=False,
        index=True,
        groups='oacis_api.group_oacis_api_admin',
        help='SHA-256 fingerprint of the key. The plaintext secret '
             'is never stored.',
    )
    scope = fields.Selection(
        string='Access Scope',
        required=True,
        default='read_only',
        selection=[
            ('read_only', 'Read Only'),
            ('notify_only', 'Notify Only'),
            ('read_write', 'Read & Write'),
            ('full', 'Full Access'),
            ('read', 'Legacy Read'),
            ('write', 'Legacy Write'),
            ('admin', 'Legacy Admin'),
        ],
        tracking=True,
    )
    expires_on = fields.Date(
        string='Expires On',
        tracking=True,
    )
    call_count = fields.Integer(
        string='Daily Call Count',
        default=0,
        readonly=True,
    )
    daily_limit = fields.Integer(
        string='Daily Limit',
        required=True,
        default=1000,
    )
    last_usage = fields.Datetime(
        string='Last Usage',
        readonly=True,
    )
    last_ip = fields.Char(
        string='Last IP Address',
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    _sql_constraints = [
        ('unique_token_hash',
         'UNIQUE(token_hash)',
         'An API key with this fingerprint already exists.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        # A brand-new key has no usable secret until an administrator
        # presses "Generate Key", which displays it exactly once.
        for vals in vals_list:
            vals.setdefault('token_hash', False)
        return super().create(vals_list)

    @api.model
    def _generate_token(self):
        return 'uck_' + secrets.token_urlsafe(45)

    @api.model
    def _hash_token(self, token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def action_generate_key(self):
        """(Re)generate the secret and show it exactly once."""
        self.ensure_one()
        raw = self._generate_token()
        self.write({
            'token_hash': self._hash_token(raw),
            'call_count': 0,
            'last_usage': False,
        })
        self.message_post(
            body=_('API key was generated/regenerated. '
                   'Any previous secret is now invalid.'),
            message_type='notification',
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Your New API Key'),
            'res_model': 'oacis.api.key.token.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_key_id': self.id,
                'default_full_token': raw,
            },
        }

    @api.model
    def validate_key(self, token, ip_address=False):
        if not token:
            raise AccessDenied(_('Invalid or inactive API key.'))
        token_hash = self._hash_token(token)
        key = self.sudo().search([
            ('token_hash', '=', token_hash),
            ('active', '=', True),
        ], limit=1)
        if not key:
            raise AccessDenied(_('Invalid or inactive API key.'))
        if key.expires_on and key.expires_on < date.today():
            raise AccessDenied(_('API key has expired.'))
        # Day boundary in the record's context timezone (UTC for
        # cron/system users) instead of naive server-local time.
        today_start = fields.Datetime.to_string(
            datetime.combine(
                fields.Date.context_today(self), time.min,
            ),
        )
        usage_count = self.sudo().search_count([
            ('id', '=', key.id),
            ('last_usage', '>=', today_start),
        ])
        if not usage_count:
            key.sudo().write({'call_count': 1})
        elif key.call_count >= key.daily_limit:
            raise ApiKeyQuotaExceeded(
                _('Daily API call limit reached.'))
        else:
            key.sudo().write({
                'call_count': key.call_count + 1,
            })
        key.sudo().write({
            'last_usage': fields.Datetime.now(),
            'last_ip': ip_address or False,
        })
        return key.sudo()


class OacisApiTokenWizard(models.TransientModel):
    _name = 'oacis.api.key.token.wizard'
    _description = 'One-time API Key Display'

    key_id = fields.Many2one('oacis.api.key', readonly=True)
    full_token = fields.Char(
        string='API Key (shown only once)',
        readonly=True,
        groups='oacis_api.group_oacis_api_admin',
    )

    def action_done(self):
        self.ensure_one()
        self.full_token = False
        return {'type': 'ir.actions.act_window_close'}
