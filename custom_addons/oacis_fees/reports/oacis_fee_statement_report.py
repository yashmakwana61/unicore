from odoo import api, models

# Reuse the currency helpers defined for the receipt report.
from .oacis_fee_receipt_report import (
    amount_to_words,
    indian_format,
)


class OacisFeeStatementReport(models.AbstractModel):
    _name = 'report.oacis_fees.fee_statement_template'
    _description = 'Student Fee Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        invoices = self.env['oacis.fee.invoice'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'oacis.fee.invoice',
            'docs': invoices,
            'amount_to_words': amount_to_words,
            'indian_format': indian_format,
            'data': data or {},
        }
