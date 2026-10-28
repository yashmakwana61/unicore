from odoo import _, fields, models


class EdicaiFacultyDocumentExt(models.Model):
    _inherit = 'edicai.faculty.member'

    document_count = fields.Integer(
        string='Documents',
        compute='_compute_faculty_doc_count',
        store=False,
    )

    def _compute_faculty_doc_count(self):
        Document = self.env['edicai.document']
        for rec in self:
            rec.document_count = Document.search_count([('faculty_member_id', '=', rec.id)])

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'edicai.document',
            'view_mode': 'list,form',
            'domain': [('faculty_member_id', '=', self.id)],
            'context': {'default_faculty_member_id': self.id},
        }
