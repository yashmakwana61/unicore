"""
UniCore Fee Accounting Configuration Model
Manages GL account mappings and invoice posting settings for fee invoices.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UniCoreFeeAccountingConfig(models.Model):
    _name = 'unicore.fee.accounting.config'
    _description = 'Fee Accounting Configuration'
    _rec_name = 'company_id'
    _check_company_auto = True

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        ondelete='restrict',
        index=True,
        help='The institution/company for which this accounting config applies',
    )

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Sales Journal',
        required=True,
        ondelete='restrict',
        domain="[('type','=','sale'),('company_id','=',company_id)]",
        help='Journal used to create student fee invoices',
    )

    revenue_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Default Revenue Account',
        required=True,
        ondelete='restrict',
        domain="[('account_type','=','income')]",
        help='Default GL revenue account for all fee lines (can be overridden per fee structure)',
    )

    receivable_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Accounts Receivable',
        ondelete='restrict',
        domain="[('account_type','=','asset_receivable')]",
        help='A/R account for student billing. If empty, uses partner default.',
    )

    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        relation='unicore_fee_config_tax_rel',
        column1='config_id',
        column2='tax_id',
        string='Default Taxes',
        domain="[('company_id','=',company_id),('type_tax_use','=','sale')]",
        help='Default taxes to apply on fee invoice lines (optional)',
    )

    auto_post_invoice = fields.Boolean(
        string='Auto-Post to GL',
        default=False,
        help="""
        If enabled: Account move is automatically posted to GL when fee invoice is confirmed.
        If disabled: Account move created as draft, user must review and post manually.
        """,
    )

    auto_create_partner = fields.Boolean(
        string='Auto-Create Student Partner',
        default=True,
        help='Automatically create res.partner record when student is created',
    )

    sync_partner_on_update = fields.Boolean(
        string='Sync Partner on Student Update',
        default=True,
        help='Automatically update res.partner when student contact details change',
    )

    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Only one active config per company',
    )

    created_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Created By',
        readonly=True,
    )

    updated_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Updated By',
        readonly=True,
    )

    _sql_constraints = [
        ('unique_company_config', 'UNIQUE(company_id)',
         'Only one active accounting configuration per institution'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['created_by_id'] = self.env.user.id
            vals['updated_by_id'] = self.env.user.id
        return super().create(vals_list)

    def write(self, vals):
        vals['updated_by_id'] = self.env.user.id
        return super().write(vals)

    @api.constrains('company_id', 'is_active')
    def _check_single_active_config(self):
        for rec in self:
            if rec.is_active:
                existing = self.search([
                    ('company_id', '=', rec.company_id.id),
                    ('is_active', '=', True),
                    ('id', '!=', rec.id),
                ])
                if existing:
                    raise ValidationError(_(
                        'Only one active accounting configuration is allowed per institution. '
                        'Deactivate the existing configuration first.'
                    ))

    @api.constrains('journal_id', 'company_id')
    def _check_journal_company_match(self):
        for rec in self:
            if rec.journal_id.company_id != rec.company_id:
                raise ValidationError(_(
                    'Journal must belong to the same institution as the configuration.'
                ))

    def _get_active_config(self, company_id=None):
        """
        Get active accounting configuration for a company.

        Args:
            company_id: res.company ID (defaults to current company)

        Returns:
            unicore.fee.accounting.config record or False
        """
        if not company_id:
            company_id = self.env.company.id

        config = self.search([
            ('company_id', '=', company_id),
            ('is_active', '=', True),
        ], limit=1)

        if not config:
            raise UserError(_(
                'No active fee accounting configuration found for %s. '
                'Please configure Fee Accounting Settings.'
            ) % self.env.company.name)

        return config
