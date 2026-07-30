from odoo import api, fields, models, _


class UniCoreStudentDocumentExt(models.Model):
    _inherit = 'unicore.student'

    document_count = fields.Integer(
        string='Doc Count',
        compute='_compute_student_doc_count',
        store=False,
    )

    def _compute_student_doc_count(self):
        Document = self.env['unicore.document']
        for rec in self:
            rec.document_count = Document.search_count([('student_id', '=', rec.id)])

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'unicore.document',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
