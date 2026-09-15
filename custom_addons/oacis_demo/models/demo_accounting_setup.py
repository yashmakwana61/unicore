"""
Oacis Demo — Accounting Setup
Loads a chart of accounts and the fee accounting configuration for the demo
company so fee invoices can be created without a "No journal could be found"
error.
"""

from odoo import _, api, models
from odoo.exceptions import UserError


class OacisDemoAccountingSetup(models.AbstractModel):
    _name = 'oacis.demo.setup'
    _description = 'Oacis Demo Accounting Setup'

    @api.model
    def _setup_accounting(self):
        self = self.sudo()
        company = self.env.ref('base.main_company')

        if not company.chart_template:
            self.env['account.chart.template'].try_loading('generic_coa', company)

        sale_journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)
        revenue_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_ids', 'in', company.id),
        ], limit=1)
        receivable_account = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_ids', 'in', company.id),
        ], limit=1)

        if not sale_journal or not revenue_account:
            raise UserError(_(
                'Could not set up demo accounting for %s: no sale journal or '
                'revenue account could be found after loading the chart of accounts.',
            ) % company.display_name)

        config = self.env['oacis.fee.accounting.config'].search([
            ('company_id', '=', company.id),
        ], limit=1)
        vals = {
            'company_id': company.id,
            'journal_id': sale_journal.id,
            'revenue_account_id': revenue_account.id,
            'receivable_account_id': receivable_account.id if receivable_account else False,
            'auto_post_invoice': False,
            'is_active': True,
        }
        if config:
            config.write(vals)
        else:
            config.create(vals)
        return True