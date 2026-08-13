"""
Oacis Fees Management Application
Standalone fee management app for Oacis ERP.
Manages fee structures, student invoicing,
payment tracking and financial reporting.
"""
from . import models


def post_init_hook(env):
    """
    Initialize accounting configuration after module installation.
    Creates default accounting config and validates GL setup.
    """
    from odoo.exceptions import UserError

    Company = env['res.company']
    AccountingConfig = env['oacis.fee.accounting.config']
    Journal = env['account.journal']
    Account = env['account.account']

    # Get all active companies
    companies = Company.search([('id', '!=', False)])

    for company in companies:
        # Check if config already exists
        existing_config = AccountingConfig.search([
            ('company_id', '=', company.id),
        ])

        if existing_config:
            continue

        try:
            revenue_account = Account.search([
                ('account_type', '=', 'income'),
                ('company_ids', 'in', company.id),
            ], limit=1)
        except Exception:
            revenue_account = Account.browse()

        try:
            receivable_account = Account.search([
                ('account_type', '=', 'asset_receivable'),
                ('company_ids', 'in', company.id),
            ], limit=1)
        except Exception:
            receivable_account = Account.browse()

        sales_journal = Journal.search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)

        try:
            bank_account = Account.search([
                ('account_type', '=', 'asset_bank'),
                ('company_ids', 'in', company.id),
            ], limit=1)
        except Exception:
            bank_account = Account.browse()

        bank_journal = Journal.search([
            ('type', 'in', ['bank', 'cash']),
            ('company_id', '=', company.id),
        ], limit=1)

        # Only create config if minimum required accounts exist
        if revenue_account and sales_journal and bank_account and bank_journal:
            try:
                AccountingConfig.create({
                    'company_id': company.id,
                    'journal_id': sales_journal.id,
                    'revenue_account_id': revenue_account.id,
                    'receivable_account_id': receivable_account.id if receivable_account else None,
                    'is_active': True,
                    'auto_post_invoice': False,
                    'auto_create_partner': True,
                    'sync_partner_on_update': True,
                })
            except Exception:
                # Silently fail - admin can set up manually
                pass
