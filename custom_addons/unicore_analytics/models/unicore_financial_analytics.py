"""
UniCore Financial Analytics
PostgreSQL VIEW-based models for fee collection
trends and financial performance analytics.
"""

from odoo import fields, models, tools
from odoo.orm.fields_misc import Id
import logging

_logger = logging.getLogger(__name__)


class UniCoreFeeCollectionReport(models.Model):
    _name = 'unicore.fee.collection.report'
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
        comodel_name='unicore.semester',
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
            'unicore_fee_collection_report'
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW
            unicore_fee_collection_report AS (
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
                FROM unicore_fee_invoice fi
                WHERE fi.invoice_state != 'cancelled'
                GROUP BY
                    fi.company_id,
                    fi.semester_id,
                    fi.invoice_state
            )
        """)


class UniCorePaymentMethodReport(models.Model):
    _name = 'unicore.payment.method.report'
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
            'unicore_payment_method_report'
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW
            unicore_payment_method_report AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    fp.company_id,
                    fp.payment_method,
                    TO_CHAR(fp.payment_date, 'YYYY-MM')
                        AS payment_month,
                    COUNT(fp.id) AS payment_count,
                    ROUND(
                        SUM(fp.amount)::numeric, 2
                    ) AS total_amount
                FROM unicore_fee_payment fp
                WHERE fp.payment_state = 'confirmed'
                GROUP BY
                    fp.company_id,
                    fp.payment_method,
                    TO_CHAR(fp.payment_date, 'YYYY-MM')
            )
        """)
