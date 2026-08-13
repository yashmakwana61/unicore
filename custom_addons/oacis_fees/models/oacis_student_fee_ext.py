"""
Oacis Student Extension — Fees Module
Adds fee summary fields to oacis.student record.
"""

import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class OacisStudentFeeExt(models.Model):
    _inherit = 'oacis.student'

    fee_invoice_ids = fields.One2many(
        comodel_name='oacis.fee.invoice',
        inverse_name='student_id',
        string='Fee Invoices',
        readonly=True,
    )
    fee_invoice_count = fields.Integer(
        string='Fee Invoices',
        compute='_compute_fee_summary',
        store=False,
    )
    total_fees_due = fields.Monetary(
        string='Total Outstanding Fees',
        compute='_compute_fee_summary',
        store=False,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        string='Currency',
        readonly=True,
    )
    has_fee_dues = fields.Boolean(
        string='Has Outstanding Fees',
        compute='_compute_fee_summary',
        store=False,
    )

    def _compute_fee_summary(self):
        for rec in self:
            invoices = rec.fee_invoice_ids.filtered(
                lambda i: i.invoice_state not in ('cancelled', 'paid'),
            )
            rec.fee_invoice_count = len(rec.fee_invoice_ids)
            rec.total_fees_due = sum(i.amount_outstanding for i in invoices)
            rec.has_fee_dues = rec.total_fees_due > 0

    def action_view_fee_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fee Invoices'),
            'res_model': 'oacis.fee.invoice',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
