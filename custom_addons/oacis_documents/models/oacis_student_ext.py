from odoo import _, fields, models


class OacisStudentDocumentExt(models.Model):
    _inherit = 'oacis.student'

    document_count = fields.Integer(
        string='Doc Count',
        compute='_compute_student_doc_count',
        store=False,
    )

    def _compute_student_doc_count(self):
        Document = self.env['oacis.document']
        for rec in self:
            rec.document_count = Document.search_count([('student_id', '=', rec.id)])

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'oacis.document',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
