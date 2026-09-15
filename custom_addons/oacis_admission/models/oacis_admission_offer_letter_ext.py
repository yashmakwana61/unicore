"""
Oacis Admission Offer Letter — Send Extension (Phase C)
Makes ``action_send`` actually send: renders the QWeb offer-letter PDF
(reports/oacis_admission_offer_letter_report.xml) and stores it as an
ir.attachment on the offer letter, then marks the letter sent.

Odoo 19 API note: ``ir.actions.report._render_qweb_pdf(report_ref, res_ids)``
returns ``(pdf_bytes, 'pdf')`` — the stream-per-resource dict only appears in
the internal ``_pre_render_qweb_pdf`` helper, never in the public method.

Automation note: the applicant transition to ``offer_sent`` is normally made by
``action_send_offer`` and ALREADY fires the automation engine through the
applicant ``write()`` override (Phase A.3). Re-firing unconditionally here would
double-send the offer email, so the engine is only called when the applicant is
still ``merit_listed`` (an offer created/sent manually before any state change).
"""

import base64

from odoo import _, models
from odoo.exceptions import UserError


class OfferLetterSendExt(models.Model):
    _inherit = 'oacis.admission.offer.letter'

    def action_send(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft offer letters can be sent.'))
            pdf_content, _fmt = self.env['ir.actions.report']._render_qweb_pdf(
                'oacis_admission.action_report_offer_letter', record.id,
            )
            if pdf_content:
                self.env['ir.attachment'].create({
                    'name': '%s.pdf' % record.letter_number,
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_content),
                    'res_model': 'oacis.admission.offer.letter',
                    'res_id': record.id,
                    'mimetype': 'application/pdf',
                })
            record.write({'state': 'sent'})
            if record.applicant_id and record.applicant_id.state == 'merit_listed':
                engine = self.env['oacis.admission.automation.engine']
                engine._fire_state_change(
                    record.applicant_id, 'merit_listed', 'offer_sent',
                )
        return True
