from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OacisDocumentCategory(models.Model):
    _name = 'oacis.document.category'
    _description = 'Document Category'
    _inherit = ['oacis.mixin']
    _order = 'sequence, name'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _check_company_auto = True

    name = fields.Char(string='Category Name', required=True)
    complete_name = fields.Char(
        string='Full Path',
        compute='_compute_complete_name',
        store=True,
        recursive=True,
    )

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_name = '%s / %s' % (
                    rec.parent_id.complete_name,
                    rec.name,
                )
            else:
                rec.complete_name = rec.name

    parent_id = fields.Many2one(
        comodel_name='oacis.document.category',
        string='Parent Category',
        ondelete='restrict',
        index=True,
        domain="[('company_id','=',company_id)]",
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        comodel_name='oacis.document.category',
        inverse_name='parent_id',
        string='Subcategories',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    category_type = fields.Selection(
        string='Category Type',
        required=True,
        default='general',
        selection=[
            ('student', 'Student Documents'),
            ('faculty', 'Faculty Documents'),
            ('institutional', 'Institutional'),
            ('template', 'Document Templates'),
            ('applicant', 'Applicant Documents'),
            ('general', 'General'),
        ],
    )
    icon = fields.Char(
        string='Icon',
        default='fa-folder',
        help='FontAwesome icon class e.g. fa-folder',
    )
    color = fields.Integer(string='Color', default=0)

    can_upload_groups = fields.Many2many(
        comodel_name='res.groups',
        relation='oacis_doc_cat_upload_group_rel',
        column1='category_id',
        column2='group_id',
        string='Upload Groups',
        help='Groups allowed to upload to this category',
    )
    can_view_groups = fields.Many2many(
        comodel_name='res.groups',
        relation='oacis_doc_cat_view_group_rel',
        column1='category_id',
        column2='group_id',
        string='View Groups',
        help='Groups allowed to view documents',
    )
    is_student_visible = fields.Boolean(
        string='Visible to Students',
        default=False,
        help='Students can see documents in this category via their portal',
    )
    is_public = fields.Boolean(
        string='Public Category',
        default=False,
        help='All portal users can view documents here',
    )

    document_count = fields.Integer(
        string='Documents',
        compute='_compute_document_count',
        store=False,
    )

    def _compute_document_count(self):
        Document = self.env['oacis.document']
        for rec in self:
            rec.document_count = Document.search_count([
                ('category_id', '=', rec.id),
            ])

    description = fields.Text(string='Description')

    _unique_name_parent_company = models.Constraint(
        'UNIQUE(name, parent_id, company_id)',
        'A category with this name already exists at this level.',
    )

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if self._has_cycle():
            raise ValidationError(_('Category hierarchy cannot be circular.'))

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s Documents') % self.name,
            'res_model': 'oacis.document',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }
