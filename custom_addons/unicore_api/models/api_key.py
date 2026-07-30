import secrets
from datetime import datetime, date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessDenied


class UniCoreApiKey(models.Model):
    _name = 'unicore.api.key'
    _description = 'API Key'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
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
    token = fields.Char(
        string='API Token',
        readonly=True,
        copy=False,
        groups='unicore_api.group_unicore_api_admin',
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
        ('unique_token',
         'UNIQUE(token)',
         'An API key with this token already exists.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = self._generate_token()
        return super().create(vals_list)

    @api.model
    def _generate_token(self):
        return 'uck_' + secrets.token_urlsafe(45)

    def action_regenerate_key(self):
        self.ensure_one()
        self.token = self._generate_token()
        self.call_count = 0
        self.last_usage = False
        self.message_post(
            body=_('API key has been regenerated.'),
            message_type='notification',
        )

    @api.model
    def validate_key(self, token, ip_address=False):
        domain = [('token', '=', token), ('active', '=', True)]
        key = self.sudo().search(domain, limit=1)
        if not key:
            raise AccessDenied(_('Invalid or inactive API key.'))
        if key.expires_on and key.expires_on < date.today():
            raise AccessDenied(_('API key has expired.'))
        today_start = fields.Datetime.to_string(
            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )
        usage_count = self.sudo().search_count([
            ('id', '=', key.id),
            ('last_usage', '>=', today_start),
        ])
        if not usage_count:
            key.sudo().write({'call_count': 1})
        elif key.call_count >= key.daily_limit:
            raise AccessDenied(_('Daily API call limit reached.'))
        else:
            key.sudo().write({
                'call_count': key.call_count + 1,
            })
        key.sudo().write({
            'last_usage': fields.Datetime.now(),
            'last_ip': ip_address or False,
        })
        return key.sudo()
