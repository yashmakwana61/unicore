"""
Edicai Financial Analytics
PostgreSQL VIEW-based models for fee collection
trends and financial performance analytics.
"""

import logging

from odoo import fields, models, tools
from odoo.orm.fields_misc import Id

_logger = logging.getLogger(__name__)


class EdicaiFeeCollectionReport(models.Model):
    _name = 'edicai.fee.collection.report'
    _description = 'Fee Collection Analytics'
    _auto = False
    _rec_name = 'semester_id'
    _order = 'semester_id desc'

    id = Id()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='edicai.semester',
        string='Semester',
        readonly=True,
    )
    invoice_state = fields.Selection(
        string='Invoice State',
        readonly=True,
        selection=[
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('partial', 'Partial'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled'),
        ],
    )
    invoice_count = fields.Integer(
        string='Invoice Count',
        readonly=True,
    )
    total_billed = fields.Float(
        string='Total Billed',
        readonly=True,
        digits=(14, 2),
    )
    total_collected = fields.Float(
        string='Total Collected',
        readonly=True,
        digits=(14, 2),
    )
    total_outstanding = fields.Float(
        string='Total Outstanding',
        readonly=True,
        digits=(14, 2),
    )
    collection_rate = fields.Float(
        string='Collection Rate %',
        readonly=True,
        digits=(5, 1),
    )

    def init(self):
        tools.drop_view_if_exists(
            self.env.cr,
            'edicai_fee_collection_report',
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW
            edicai_fee_collection_report AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    fi.company_id,
                    fi.semester_id,
                    fi.invoice_state,
                    COUNT(fi.id) AS invoice_count,
                    ROUND(
                        SUM(fi.total_amount)::numeric, 2
                    ) AS total_billed,
                    ROUND(
                        SUM(fi.amount_paid)::numeric, 2
                    ) AS total_collected,
                    ROUND(
                        SUM(fi.amount_outstanding)
                        ::numeric, 2
                    ) AS total_outstanding,
                    ROUND(
                        (SUM(fi.amount_paid)::numeric
                        / NULLIF(SUM(fi.total_amount), 0)
                        * 100), 1
                    ) AS collection_rate
                FROM edicai_fee_invoice fi
                WHERE fi.invoice_state IN
                    ('sent', 'partial', 'paid',
                     'overdue')
                GROUP BY
                    fi.company_id,
                    fi.semester_id,
                    fi.invoice_state
            )
        """)


class EdicaiPaymentMethodReport(models.Model):
    _name = 'edicai.payment.method.report'
    _description = 'Payment Method Analytics'
    _auto = False
    _rec_name = 'payment_method'
    _order = 'payment_month desc, payment_method'

    id = Id()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        readonly=True,
    )
    payment_method = fields.Selection(
        string='Payment Method',
        readonly=True,
        selection=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('cheque', 'Cheque'),
            ('online', 'Online'),
            ('dd', 'Demand Draft'),
            ('upi', 'UPI'),
            ('card', 'Card'),
            ('scholarship', 'Scholarship'),
            ('waiver', 'Waiver'),
        ],
    )
    payment_month = fields.Char(
        string='Month',
        readonly=True,
    )
    payment_count = fields.Integer(
        string='Payments',
        readonly=True,
    )
    total_amount = fields.Float(
        string='Total Amount',
        readonly=True,
        digits=(14, 2),
    )

    def init(self):
        tools.drop_view_if_exists(
            self.env.cr,
            'edicai_payment_method_report',
        )
        cr = self.env.cr
        # `payment` module is optional (only pulled in
        # via edicai_payment). Guard online-transaction
        # detection so the VIEW still builds when the
        # payment tables are absent.
        cr.execute(
            "SELECT to_regclass('public.payment_transaction')"
        )
        has_tx = bool(cr.fetchone()[0])
        cr.execute(
            "SELECT to_regclass("
            "'public.payment_transaction_invoice_ids')"
        )
        has_tx_rel = bool(cr.fetchone()[0])
        has_online = has_tx and has_tx_rel

        if has_online:
            online_exists = """
                EXISTS (
                    SELECT 1
                    FROM payment_transaction_invoice_ids rel
                    JOIN payment_transaction pt
                        ON pt.id = rel.transaction_id
                    WHERE rel.invoice_id
                        = fi.account_move_id
                      AND pt.state = 'done'
                )"""
            gl_month = """
                TO_CHAR(COALESCE(
                    (
                        SELECT MAX(pt.create_date)::date
                        FROM payment_transaction_invoice_ids
                            rel
                        JOIN payment_transaction pt
                            ON pt.id = rel.transaction_id
                        WHERE rel.invoice_id
                            = fi.account_move_id
                          AND pt.state = 'done'
                    ),
                    am.invoice_date,
                    fi.invoice_date,
                    CURRENT_DATE
                ), 'YYYY-MM')"""
        else:
            online_exists = "FALSE"
            gl_month = """
                TO_CHAR(COALESCE(
                    am.invoice_date,
                    fi.invoice_date,
                    CURRENT_DATE
                ), 'YYYY-MM')"""

        # Primary source: GL-collected residual per fee
        # invoice (authoritative collected amount, same
        # expression as the finance snapshot). Method is
        # 'online' when a done payment.transaction is
        # linked to the GL move, else the dominant
        # confirmed legacy receipt method, else
        # 'bank_transfer' (standard GL register-payment
        # default). Legacy receipts are only counted for
        # invoices with no GL move (fallback), so no
        # payment is ever counted twice.
        cr.execute("""
            CREATE OR REPLACE VIEW
            edicai_payment_method_report AS (
                WITH gl_sourced AS (
                    SELECT
                        fi.company_id,
                        CASE
                            WHEN %(online_exists)s
                                THEN 'online'
                            WHEN (
                                SELECT fp.payment_method
                                FROM edicai_fee_payment fp
                                WHERE fp.invoice_id = fi.id
                                  AND fp.payment_state
                                      = 'confirmed'
                                ORDER BY fp.amount DESC
                                LIMIT 1
                            ) IS NOT NULL THEN (
                                SELECT fp.payment_method
                                FROM edicai_fee_payment fp
                                WHERE fp.invoice_id = fi.id
                                  AND fp.payment_state
                                      = 'confirmed'
                                ORDER BY fp.amount DESC
                                LIMIT 1
                            )
                            ELSE 'bank_transfer'
                        END AS payment_method,
                        %(gl_month)s AS payment_month,
                        GREATEST(
                            fi.total_amount
                            - fi.amount_outstanding, 0
                        ) AS amount
                    FROM edicai_fee_invoice fi
                    LEFT JOIN account_move am
                        ON am.id = fi.account_move_id
                    WHERE fi.account_move_id IS NOT NULL
                      AND fi.invoice_state NOT IN
                          ('draft', 'cancelled')
                ),
                legacy_fallback AS (
                    SELECT
                        fp.company_id,
                        fp.payment_method,
                        TO_CHAR(fp.payment_date, 'YYYY-MM')
                            AS payment_month,
                        fp.amount AS amount
                    FROM edicai_fee_payment fp
                    JOIN edicai_fee_invoice fi
                        ON fi.id = fp.invoice_id
                    WHERE fp.payment_state = 'confirmed'
                      AND fi.account_move_id IS NULL
                      AND fi.invoice_state NOT IN
                          ('draft', 'cancelled')
                ),
                combined AS (
                    SELECT * FROM gl_sourced
                    UNION ALL
                    SELECT * FROM legacy_fallback
                )
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    company_id,
                    payment_method,
                    payment_month,
                    COUNT(*) AS payment_count,
                    ROUND(
                        SUM(amount)::numeric, 2
                    ) AS total_amount
                FROM combined
                WHERE amount > 0
                GROUP BY
                    company_id,
                    payment_method,
                    payment_month
            )
        """ % {
            'online_exists': online_exists,
            'gl_month': gl_month,
        })
