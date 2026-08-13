from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OacisStudentDocument(models.Model):
    """Student document records for identity proofs, transcripts, certificates etc."""

    _name = 'oacis.student.document'
    _description = 'Student Document'
    _inherit = ['oacis.mixin', 'mail.thread']
    _order = 'is_verified, document_type, name'
    _check_company_auto = True
    _rec_name = 'name'

    name = fields.Char(string='Document Name', required=True, tracking=True)
    document_type = fields.Selection(
        selection=[
            ('id_proof', 'ID Proof'),
            ('passport', 'Passport'),
            ('visa', 'Visa / I-20'),
            ('birth_certificate', 'Birth Certificate'),
            ('transcript', 'Transcript / Marksheet'),
            ('degree_certificate', 'Degree Certificate'),
            ('migration', 'Migration Certificate'),
            ('transfer', 'Transfer Certificate'),
            ('character', 'Character Certificate'),
            ('medical', 'Medical Certificate'),
            ('fee_receipt', 'Fee Receipt'),
            ('scholarship', 'Scholarship Document'),
            ('achievement', 'Achievement Certificate'),
            ('other', 'Other'),
        ],
        string='Document Type', required=True, tracking=True,
    )
    file = fields.Binary(string='File', attachment=True, required=True)
    file_name = fields.Char(string='File Name')
    file_size = fields.Integer(string='File Size (bytes)')
    file_mime_type = fields.Char(string='MIME Type')
    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date')
    issuing_authority = fields.Char(string='Issuing Authority')
    reference_number = fields.Char(string='Reference Number')
    remarks = fields.Text(string='Remarks')

    is_verified = fields.Boolean(string='Verified', default=False, tracking=True)
    verified_by = fields.Many2one(
        comodel_name='res.users', string='Verified By',
        readonly=True, copy=False,
    )
    verified_on = fields.Datetime(string='Verified On', readonly=True, copy=False)
    verification_notes = fields.Text(string='Verification Notes')

    student_id = fields.Many2one(
        comodel_name='oacis.student', string='Student',
        required=True, ondelete='cascade',
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        related='student_id.company_id', store=True, readonly=True,
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus', string='Campus',
        related='student_id.campus_id', store=True, readonly=True,
    )

    sequence = fields.Integer(string='Sequence', default=10)

    _check_file = models.Constraint(
        "CHECK(file IS NOT NULL)",
        'Document file is required.',
    )

    @api.constrains('expiry_date', 'issue_date')
    def _check_dates(self):
        for record in self:
            if record.expiry_date and record.issue_date and record.expiry_date <= record.issue_date:
                raise ValidationError(
                    _('Expiry date must be after the issue date for document: %s') % record.name,
                )

    def action_verify(self):
        for record in self:
            record.write({
                'is_verified': True,
                'verified_by': self.env.user.id,
                'verified_on': fields.Datetime.now(),
            })

    def action_unverify(self):
        for record in self:
            record.write({
                'is_verified': False,
                'verified_by': False,
                'verified_on': False,
            })
