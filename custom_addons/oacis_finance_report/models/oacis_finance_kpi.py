"""
Oacis Finance KPI Model
Stores computed Key Performance Indicators for
financial reporting. Provides the data layer for
the dashboard view. KPIs are computed on-demand
via a wizard or refreshed by the cron job.
"""

import logging
from datetime import date

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class OacisFinanceKPI(models.Model):
    _name = 'oacis.finance.kpi'
    _description = 'Financial KPI Record'
    _rec_name = 'display_name'
    _inherit = ['oacis.mixin']

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['company_id.display_name', 'semester_id.display_name',
                 'kpi_date'],
    )

    @api.depends('company_id.display_name', 'semester_id.display_name',
                 'kpi_date')
    def _compute_display_name(self):
        for rec in self:
            context = (
                rec.semester_id.display_name
                or rec.company_id.display_name
                or ''
            )
            if rec.kpi_date:
                rec.display_name = '%s - %s' % (
                    context,
                    rec.kpi_date.strftime('%b %Y'),
                )
            else:
                rec.display_name = context
    _order = 'company_id, kpi_date desc'
    _check_company_auto = True

    kpi_date = fields.Date(
        string='KPI Date',
        required=True,
        default=fields.Date.today,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    semester_id = fields.Many2one(
        comodel_name='oacis.semester',
        string='Semester',
        ondelete='set null',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    # --- REVENUE KPIs ---

    total_billed = fields.Monetary(
        string='Total Billed',
        currency_field='currency_id',
        default=0.0,
    )
    total_collected = fields.Monetary(
        string='Total Collected',
        currency_field='currency_id',
        default=0.0,
    )
    total_outstanding = fields.Monetary(
        string='Total Outstanding',
        currency_field='currency_id',
        default=0.0,
    )
    collection_efficiency = fields.Float(
        string='Collection Efficiency (%)',
        default=0.0,
        digits=(5, 2),
    )

    # --- STUDENT KPIs ---

    total_students_billed = fields.Integer(
        string='Students Billed',
        default=0,
    )
    total_students_paid = fields.Integer(
        string='Students Fully Paid',
        default=0,
    )
    total_students_overdue = fields.Integer(
        string='Students Overdue',
        default=0,
    )
    total_students_scholarship = fields.Integer(
        string='Scholarship Recipients',
        default=0,
    )

    # --- PAYMENT METHOD BREAKDOWN ---

    cash_collected = fields.Monetary(
        string='Cash Collected',
        currency_field='currency_id',
        default=0.0,
    )
    online_collected = fields.Monetary(
        string='Online Collected',
        currency_field='currency_id',
        default=0.0,
    )
    bank_transfer_collected = fields.Monetary(
        string='Bank Transfer',
        currency_field='currency_id',
        default=0.0,
    )
    other_collected = fields.Monetary(
        string='Other Methods',
        currency_field='currency_id',
        default=0.0,
    )

    @api.model
    def compute_kpi(self, company_id, semester_id=False):
        """
        Compute and store KPI for given company
        and optional semester. Called from dashboard
        refresh button and cron job.
        """
        today = date.today()

        # Aggregate in SQL: avoids full recordset loads and
        # counts distinct students correctly; for legacy
        # payments it also includes archived rows that the
        # ORM search silently drops.
        semester_clause = (
            ' AND semester_id = %s' if semester_id else ''
        )
        inv_params = [company_id] + (
            [semester_id] if semester_id else []
        )
        self.env.cr.execute(
            """
            SELECT
                COALESCE(SUM(total_amount), 0),
                COALESCE(SUM(amount_outstanding), 0),
                COUNT(DISTINCT CASE WHEN invoice_state
                    = 'paid' THEN student_id END),
                COUNT(DISTINCT CASE WHEN invoice_state
                    = 'overdue' THEN student_id END)
            FROM oacis_fee_invoice
            WHERE company_id = %s
              AND invoice_state NOT IN ('draft', 'cancelled')
            """ + semester_clause,
            inv_params,
        )
        (total_billed,
         total_outstanding,
         paid_student_count,
         overdue_student_count) = self.env.cr.fetchone()

        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(collected), 0)
            FROM (
                SELECT CASE
                    WHEN fi.account_move_id IS NOT NULL
                        THEN GREATEST(
                            fi.total_amount
                            - fi.amount_outstanding, 0)
                    ELSE COALESCE((
                        SELECT SUM(fp.amount)
                        FROM oacis_fee_payment fp
                        WHERE fp.invoice_id = fi.id
                          AND fp.payment_state
                              = 'confirmed'
                    ), 0)
                END AS collected
                FROM oacis_fee_invoice fi
                WHERE fi.company_id = %s
                  AND fi.invoice_state NOT IN
                      ('draft', 'cancelled')
            """ + (
                " AND fi.semester_id = %s"
                if semester_id else ""
            ) + """
            ) sub
            """,
            [company_id] + (
                [semester_id] if semester_id else []
            ),
        )
        # GL-aware collection total: reconciled residual for
        # GL invoices, confirmed legacy receipts otherwise.
        total_collected = self.env.cr.fetchone()[0]

        self.env.cr.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN payment_method
                    = 'cash' THEN amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN payment_method IN
                    ('online', 'upi', 'card')
                    THEN amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN payment_method IN
                    ('bank_transfer', 'cheque', 'dd')
                    THEN amount ELSE 0 END), 0)
            FROM oacis_fee_payment
            WHERE company_id = %s
              AND payment_state = 'confirmed'
            """,
            [company_id],
        )
        (cash, online, bank) = self.env.cr.fetchone()
        collection_efficiency = (
            round(
                total_collected / total_billed * 100, 2,
            )
            if total_billed > 0 else 0.0
        )

        other = total_collected - cash - online - bank

        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(award_amount), 0),
                   COUNT(DISTINCT student_id)
            FROM oacis_scholarship_award
            WHERE company_id = %s
              AND award_state = 'disbursed'
            """,
            [company_id],
        )
        scholarship_total, scholarship_students_len = (
            self.env.cr.fetchone()
        )

        self.env.cr.execute(
            """
            SELECT COUNT(DISTINCT student_id)
            FROM oacis_fee_invoice
            WHERE company_id = %s
              AND invoice_state NOT IN ('draft', 'cancelled')
            """ + semester_clause,
            inv_params,
        )
        billed_student_count = (
            self.env.cr.fetchone()[0]
        )

        company = self.env['res.company'].browse(
            company_id,
        )

        vals = {
            'kpi_date': today,
            'company_id': company_id,
            'semester_id': semester_id or False,
            'currency_id': company.currency_id.id,
            'total_billed': float(total_billed),
            'total_collected': float(total_collected),
            'total_outstanding': float(total_outstanding),
            'collection_efficiency': collection_efficiency,
            'total_students_billed': billed_student_count,
            'total_students_paid': paid_student_count,
            'total_students_overdue': (
                overdue_student_count
            ),
            'total_students_scholarship': (
                scholarship_students_len
            ),
            'cash_collected': float(cash),
            'online_collected': float(online),
            'bank_transfer_collected': float(bank),
            'other_collected': float(other),
        }

        existing = self.search([
            ('kpi_date', '=', today),
            ('company_id', '=', company_id),
            ('semester_id', '=', semester_id or False),
        ], limit=1)

        if existing:
            existing.write(vals)
            return existing
        return self.create(vals)
