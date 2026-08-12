"""
UniCore Finance KPI Model
Stores computed Key Performance Indicators for
financial reporting. Provides the data layer for
the dashboard view. KPIs are computed on-demand
via a wizard or refreshed by the cron job.
"""

import logging
from datetime import date

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class UniCoreFinanceKPI(models.Model):
    _name = 'unicore.finance.kpi'
    _description = 'Financial KPI Record'
    _rec_name = 'display_name'
    _inherit = ['unicore.mixin']

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
        comodel_name='unicore.semester',
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
        Invoice = self.env['unicore.fee.invoice']
        Payment = self.env['unicore.fee.payment']
        Award = self.env['unicore.scholarship.award']

        inv_domain = [
            ('company_id', '=', company_id),
            ('invoice_state', 'not in',
             ['draft', 'cancelled']),
        ]
        if semester_id:
            inv_domain.append(
                ('semester_id', '=', semester_id),
            )

        invoices = Invoice.search(inv_domain)
        confirmed_payments = Payment.search([
            ('company_id', '=', company_id),
            ('payment_state', '=', 'confirmed'),
        ])

        total_billed = sum(
            i.total_amount for i in invoices
        )
        total_collected = sum(
            p.amount for p in confirmed_payments
        )
        total_outstanding = sum(
            i.amount_outstanding for i in invoices
        )
        collection_efficiency = (
            round(
                total_collected / total_billed * 100, 2,
            )
            if total_billed > 0 else 0.0
        )

        paid_students = invoices.filtered(
            lambda i: i.invoice_state == 'paid',
        ).mapped('student_id')
        overdue_students = invoices.filtered(
            lambda i: i.invoice_state == 'overdue',
        ).mapped('student_id')

        awards = Award.search([
            ('company_id', '=', company_id),
            ('award_state', '=', 'disbursed'),
        ])
        scholarship_students = set(
            awards.mapped('student_id').ids,
        )

        cash = sum(
            p.amount for p in confirmed_payments
            if p.payment_method == 'cash'
        )
        online = sum(
            p.amount for p in confirmed_payments
            if p.payment_method in ('online', 'upi', 'card')
        )
        bank = sum(
            p.amount for p in confirmed_payments
            if p.payment_method in ('bank_transfer',
                                     'cheque', 'dd')
        )
        other = total_collected - cash - online - bank

        company = self.env['res.company'].browse(
            company_id,
        )

        vals = {
            'kpi_date': today,
            'company_id': company_id,
            'semester_id': semester_id or False,
            'currency_id': company.currency_id.id,
            'total_billed': total_billed,
            'total_collected': total_collected,
            'total_outstanding': total_outstanding,
            'collection_efficiency': collection_efficiency,
            'total_students_billed': len(invoices),
            'total_students_paid': len(paid_students),
            'total_students_overdue': len(
                overdue_students,
            ),
            'total_students_scholarship': len(
                scholarship_students,
            ),
            'cash_collected': cash,
            'online_collected': online,
            'bank_transfer_collected': bank,
            'other_collected': other,
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
