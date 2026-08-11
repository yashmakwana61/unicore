from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DigitalMaterial(models.Model):
    _name = 'unicore.digital.material'
    _description = 'Digital Library Material'
    _inherit = ['unicore.mixin']
    _order = 'title'
    _check_company_auto = True

    title = fields.Char(string='Title', required=True)
    author = fields.Char(string='Author/Creator')
    subject_id = fields.Many2one(
        'unicore.library.subject',
        string='Subject',
    )
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)
    file_type = fields.Selection([
        ('pdf', 'PDF Document'),
        ('epub', 'EPUB eBook'),
        ('audio', 'Audiobook (MP3/WAV)'),
        ('video', 'Video (MP4)'),
        ('other', 'Other')
    ], string='File Type', required=True, default='pdf')
    file_name = fields.Char(string='File Name')
    file_content = fields.Binary(
        string='File Content',
        required=True,
        attachment=True,
    )
    access_level = fields.Selection([
        ('all', 'All Users'),
        ('enrolled_only', 'Enrolled Students Only'),
        ('faculty_only', 'Faculty Only')
    ], string='Access Level', required=True, default='enrolled_only')
    description = fields.Text(string='Description')

    def check_access_rights(self, operation, raise_exception=True):
        res = super().check_access_rights(operation, raise_exception=raise_exception)
        return res
