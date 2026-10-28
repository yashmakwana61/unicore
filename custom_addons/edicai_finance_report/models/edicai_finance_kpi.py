"""
Edicai Finance KPI Model
Stores computed Key Performance Indicators for
financial reporting. Provides the data layer for
the dashboard view. KPIs are computed on-demand
via a wizard or refreshed by the cron job.
"""

import logging
from datetime import date

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EdicaiFinanceKPI(models.Model):
    _name = 'edicai.finance.kpi'
    _description = 'Financial KPI Record'
    _rec_name = 'display_name'
    _inherit = ['edicai.mixin']

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
        comodel_name='edicai.semester',
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
            FROM edicai_fee_invoice
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
                        FROM edicai_fee_payment fp
                        WHERE fp.invoice_id = fi.id
                          AND fp.payment_state
                              = 'confirmed'
                    ), 0)
                END AS collected
                FROM edicai_fee_invoice fi
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

        # Detect optional payment tables (`payment`
        # module is only present via edicai_payment).
        self.env.cr.execute(
            "SELECT to_regclass("
            "'public.payment_transaction')"
        )
        has_tx = bool(self.env.cr.fetchone()[0])
        self.env.cr.execute(
            "SELECT to_regclass("
            "'public.payment_transaction_invoice_ids')"
        )
        has_tx_rel = bool(self.env.cr.fetchone()[0])
        if has_tx and has_tx_rel:
            online_exists = """
                EXISTS (
                    SELECT 1
                    FROM payment_transaction_invoice_ids
                        rel
                    JOIN payment_transaction pt
                        ON pt.id = rel.transaction_id
                    WHERE rel.invoice_id
                        = fi.account_move_id
                      AND pt.state = 'done'
                )"""
        else:
            online_exists = "FALSE"

        sem_filter = (
            " AND fi.semester_id = %s"
            if semester_id else ""
        )
        method_params = (
            [company_id]
            + ([semester_id] if semester_id else [])
            + [company_id]
            + ([semester_id] if semester_id else [])
        )
        # GL-sourced method split (mirrors the payment
        # method report VIEW): each GL invoice's
        # reconciled residual is attributed once —
        # 'online' when a done payment.transaction is
        # linked to its GL move, else the dominant
        # confirmed legacy receipt method, else
        # 'bank_transfer'. Legacy receipts are only
        # summed for invoices with no GL move, so no
        # payment is counted twice.
        self.env.cr.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN method
                    = 'cash' THEN amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN method IN
                    ('online', 'upi', 'card')
                    THEN amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN method IN
                    ('bank_transfer', 'cheque', 'dd')
                    THEN amount ELSE 0 END), 0)
            FROM (
                SELECT
                    CASE
                        WHEN gl.online_flag
                            THEN 'online'
                        WHEN gl.dom_method IS NOT NULL
                            THEN gl.dom_method
                        ELSE 'bank_transfer'
                    END AS method,
                    gl.gl_collected AS amount
                FROM (
                    SELECT
                        GREATEST(
                            fi.total_amount
                            - fi.amount_outstanding, 0
                        ) AS gl_collected,
                        (""" + online_exists + """) AS online_flag,
                        (
                            SELECT fp.payment_method
                            FROM edicai_fee_payment fp
                            WHERE fp.invoice_id = fi.id
                              AND fp.payment_state
                                  = 'confirmed'
                            ORDER BY fp.amount DESC
                            LIMIT 1
                        ) AS dom_method
                    FROM edicai_fee_invoice fi
                    WHERE fi.company_id = %s
                      AND fi.invoice_state NOT IN
                          ('draft', 'cancelled')
                      AND fi.account_move_id IS NOT NULL
                    """ + sem_filter + """
                ) gl
                UNION ALL
                SELECT fp.payment_method AS method,
                       fp.amount AS amount
                FROM edicai_fee_payment fp
                JOIN edicai_fee_invoice fi
                    ON fi.id = fp.invoice_id
                WHERE fi.company_id = %s
                  AND fp.payment_state = 'confirmed'
                  AND fi.account_move_id IS NULL
                  AND fi.invoice_state NOT IN
                      ('draft', 'cancelled')
                """ + sem_filter + """
            ) sub
            """,
            method_params,
        )
        (cash, online, bank) = self.env.cr.fetchone()
        collection_efficiency = (
            round(
                total_collected / total_billed * 100, 2,
            )
            if total_billed > 0 else 0.0
        )

        other = total_collected - cash - online - bank
        if other < 0:
            # Defensive: method parts must never exceed
            # the GL-aware total (double-count symptom,
            # e.g. a receipt recorded in both GL and
            # legacy). Clamp instead of storing a
            # negative breakdown bucket.
            _logger.warning(
                'Negative other_collected (%.2f) for '
                'company %s semester %s: payment method '
                'parts exceed total_collected; clamped '
                'to 0.',
                float(other), company_id,
                semester_id or False,
            )
            other = 0.0

        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(sa.award_amount), 0),
                   COUNT(DISTINCT sa.student_id)
            FROM edicai_scholarship_award sa
            LEFT JOIN edicai_fee_invoice fi
                ON fi.id = sa.fee_invoice_id
                AND fi.company_id = sa.company_id
            WHERE sa.company_id = %s
              AND sa.award_state = 'disbursed'
            """ + (
                " AND COALESCE(fi.semester_id, "
                "sa.semester_id) = %s"
                if semester_id else ""
            ),
            [company_id] + (
                [semester_id] if semester_id else []
            ),
        )
        scholarship_total, scholarship_students_len = (
            self.env.cr.fetchone()
        )

        self.env.cr.execute(
            """
            SELECT COUNT(DISTINCT student_id)
            FROM edicai_fee_invoice
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
