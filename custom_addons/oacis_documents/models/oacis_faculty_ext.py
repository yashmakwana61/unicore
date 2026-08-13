from odoo import _, fields, models


class UniCoreFacultyDocumentExt(models.Model):
    _inherit = 'unicore.faculty.member'

    document_count = fields.Integer(
        string='Documents',
        compute='_compute_faculty_doc_count',
        store=False,
    )

    def _compute_faculty_doc_count(self):
        Document = self.env['unicore.document']
        for rec in self:
            rec.document_count = Document.search_count([('faculty_member_id', '=', rec.id)])

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'unicore.document',
            'view_mode': 'list,form',
            'domain': [('faculty_member_id', '=', self.id)],
            'context': {'default_faculty_member_id': self.id},
        }
