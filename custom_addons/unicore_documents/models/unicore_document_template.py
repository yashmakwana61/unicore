from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class UniCoreDocumentTemplate(models.Model):
    _name = 'unicore.document.template'
    _description = 'Document Template'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'template_type, name'
    _check_company_auto = True

    name = fields.Char(string='Template Name', required=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    template_type = fields.Selection(
        string='Document Type',
        required=True,
        default='bonafide',
        selection=[
            ('bonafide', 'Bonafide Letter'),
            ('transcript', 'Academic Transcript'),
            ('noc', 'No Objection Certificate'),
            ('experience', 'Experience Letter'),
            ('admission', 'Admission Confirmation'),
            ('scholarship', 'Scholarship Certificate'),
            ('completion', 'Completion Certificate'),
            ('merit', 'Merit Certificate'),
            ('conduct', 'Good Conduct Certificate'),
            ('custom', 'Custom Template'),
        ],
    )
    subject = fields.Char(string='Document Title / Subject', required=True)
    body_html = fields.Html(
        string='Document Body',
        required=True,
        help='HTML body with {variable} placeholders. '
             'Available variables: '
             '{student_name}, {student_id}, '
             '{program_name}, {academic_year}, '
             '{institution_name}, {principal_name}, '
             '{today_date}, {semester_name}',
    )
    header_text = fields.Char(
        string='Header Text',
        help='Text shown in document header/letterhead',
    )
    footer_text = fields.Text(string='Footer Text')
    signatory_name = fields.Char(string='Signatory Name')
    signatory_designation = fields.Char(string='Signatory Designation')
    is_system_template = fields.Boolean(string='System Template', default=False)
    is_active_template = fields.Boolean(string='Template Active', default=True)
    generated_count = fields.Integer(
        string='Generated Count',
        compute='_compute_generated_count',
        store=False,
    )

    def _compute_generated_count(self):
        Document = self.env['unicore.document']
        for rec in self:
            rec.generated_count = Document.search_count([
                ('document_type', '=', 'template'),
                ('name', 'ilike', rec.name),
            ])

    def action_generate_for_student(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Document'),
            'res_model': 'unicore.document.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_template_id': self.id},
        }

    def generate_for_student(self, student_id):
        self.ensure_one()
        student = self.env['unicore.student'].browse(student_id)
        if not student.exists():
            raise UserError(_('Student record not found.'))

        from datetime import date
        variables = {
            'student_name': student.display_name,
            'student_id': student.student_id_number,
            'program_name': student.program_id.name if student.program_id else '',
            'academic_year': (
                student.current_semester_id.academic_year_id.name
                if student.current_semester_id and student.current_semester_id.academic_year_id
                else ''
            ),
            'semester_name': student.current_semester_id.name if student.current_semester_id else '',
            'institution_name': student.company_id.name,
            'today_date': str(date.today()),
            'principal_name': self.signatory_name or '',
        }

        try:
            rendered_body = self.body_html
            if isinstance(rendered_body, str):
                for key, val in variables.items():
                    rendered_body = rendered_body.replace('{%s}' % key, str(val))
        except Exception as e:
            _logger.error('Template render error: %s', str(e))
            rendered_body = self.body_html

        category = self.env['unicore.document.category'].search([
            ('category_type', '=', 'student'),
            ('company_id', '=', student.company_id.id),
            ('parent_id', '=', False),
        ], limit=1)

        doc_name = '%s -- %s' % (self.subject, student.display_name)
        document = self.env['unicore.document'].create({
            'name': doc_name,
            'company_id': student.company_id.id,
            'category_id': category.id if category else False,
            'document_type': 'bonafide',
            'student_id': student.id,
            'upload_date': date.today(),
            'document_state': 'active',
            'is_student_visible': True,
            'description': _('Generated from template: %s') % self.name,
        })
        self.message_post(
            body=_('Document generated for %s: %s') % (student.display_name, doc_name)
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Document'),
            'res_model': 'unicore.document',
            'res_id': document.id,
            'view_mode': 'form',
            'target': 'current',
        }
