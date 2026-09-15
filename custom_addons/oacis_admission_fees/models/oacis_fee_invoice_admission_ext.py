"""
Oacis Fee Invoice — Admission Bridge (Phase D)

Links ``oacis.fee.invoice`` back to the admission applicant and auto-confirms
the admission once the invoice is fully paid.

The link field is defined here (not in ``oacis_fees``) because only this bridge
module can depend on both ``oacis_fees`` and ``oacis_admission``.
"""

from odoo import _, api, fields, models


class OacisFeeInvoiceAdmissionExt(models.Model):
    _inherit = 'oacis.fee.invoice'

    applicant_id = fields.Many2one(
        comodel_name='oacis.admission.applicant',
        string='Admission Applicant',
        ondelete='set null',
        index=True,
        help='Admission applicant this invoice was generated for (bridge '
             'between oacis_admission and oacis_fees).',
    )

    def _update_payment_state(self):
        super()._update_payment_state()
        self._confirm_applicant_if_paid()

    def _confirm_applicant_if_paid(self):
        """Auto-confirm the linked admission when the invoice is fully paid."""
        for invoice in self:
            if (invoice.invoice_state == 'paid'
                    and invoice.applicant_id
                    and invoice.applicant_id.state == 'fee_pending'):
                applicant = invoice.applicant_id.with_company(
                    invoice.company_id)
                applicant.action_confirm_admission()
                invoice.message_post(body=_(
                    'Admission automatically confirmed for %s after full '
                    'fee payment.',
                ) % applicant.name)