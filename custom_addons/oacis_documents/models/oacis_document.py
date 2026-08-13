from odoo import _, api, fields, models
from odoo.exceptions import UserError


class UniCoreDocument(models.Model):
    _name = 'unicore.document'
    _description = 'Document'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'category_id, upload_date desc'
    _check_company_auto = True
    _rec_name = 'name'

    name = fields.Char(string='Document Name', required=True, tracking=True)
    document_number = fields.Char(
        string='Document Reference',
        index=True,
        help='Official reference number if applicable',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    category_id = fields.Many2one(
        comodel_name='unicore.document.category',
        string='Category / Folder',
        required=True,
        ondelete='restrict',
        index=True,
        domain="[('company_id','=',company_id)]",
        tracking=True,
    )
    category_type = fields.Selection(
        string='Category Type',
        related='category_id.category_type',
        store=True,
        readonly=True,
    )
    document_type = fields.Selection(
        string='Document Type',
        required=True,
        default='other',
        selection=[
            ('marksheet', 'Marksheet / Transcript'),
            ('certificate', 'Certificate / Degree'),
            ('id_proof', 'ID Proof'),
            ('bonafide', 'Bonafide Letter'),
            ('fee_receipt', 'Fee Receipt'),
            ('admission_letter', 'Admission Letter'),
            ('noc', 'No Objection Certificate'),
            ('appointment_letter', 'Appointment Letter'),
            ('contract', 'Employment Contract'),
            ('experience_letter', 'Experience Letter'),
            ('qualification_cert', 'Qualification Certificate'),
            ('policy', 'Policy Document'),
            ('circular', 'Circular / Notice'),
            ('academic_calendar', 'Academic Calendar'),
            ('meeting_minutes', 'Meeting Minutes'),
            ('audit_report', 'Audit Report'),
            ('accreditation', 'Accreditation Document'),
            ('template', 'Document Template'),
            ('other', 'Other'),
        ],
    )
    tags = fields.Char(string='Tags', help='Comma-separated tags for quick search')

    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        ondelete='set null',
        index=True,
        domain="[('company_id','=',company_id)]",
    )
    faculty_member_id = fields.Many2one(
        comodel_name='unicore.faculty.member',
        string='Faculty Member',
        ondelete='set null',
        index=True,
        domain="[('company_id','=',company_id)]",
    )
    applicant_id = fields.Many2one(
        comodel_name='unicore.admission.applicant',
        string='Applicant',
        ondelete='set null',
        domain="[('company_id','=',company_id)]",
    )

    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='unicore_document_attachment_rel',
        column1='document_id',
        column2='attachment_id',
        string='Files',
    )
    file_count = fields.Integer(
        string='File Count',
        compute='_compute_file_count',
        store=False,
    )

    def _compute_file_count(self):
        for rec in self:
            rec.file_count = len(rec.attachment_ids)

    primary_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='Primary File',
        ondelete='set null',
        help='The main file for this document record',
    )
    file_type = fields.Char(
        string='File Type',
        related='primary_attachment_id.mimetype',
        store=False,
        readonly=True,
    )
    file_size = fields.Integer(
        string='File Size (bytes)',
        related='primary_attachment_id.file_size',
        store=False,
        readonly=True,
    )

    upload_date = fields.Date(
        string='Upload Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    document_date = fields.Date(
        string='Document Date',
        help='Date on the actual document',
    )
    expiry_date = fields.Date(
        string='Expiry Date',
        tracking=True,
        help='Date when document expires (e.g. ID proof validity)',
    )
    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired',
        store=False,
    )

    @api.depends('expiry_date')
    def _compute_is_expired(self):
        from datetime import date
        today = date.today()
        for rec in self:
            rec.is_expired = bool(rec.expiry_date) and rec.expiry_date < today

    is_verified = fields.Boolean(string='Verified', default=False, tracking=True)
    verified_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Verified By',
        readonly=True,
    )
    verified_on = fields.Date(string='Verified On', readonly=True)
    verification_notes = fields.Text(string='Verification Notes')

    version = fields.Integer(string='Version', default=1, readonly=True)
    previous_version_id = fields.Many2one(
        comodel_name='unicore.document',
        string='Previous Version',
        ondelete='set null',
    )
    is_latest_version = fields.Boolean(string='Latest Version', default=True)

    is_confidential = fields.Boolean(
        string='Confidential',
        default=False,
        tracking=True,
        help='Restrict access to admin only',
    )
    is_student_visible = fields.Boolean(
        string='Visible to Student',
        default=False,
        help='Student can view via portal',
    )

    document_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('archived', 'Archived'),
            ('expired', 'Expired'),
        ],
    )

    description = fields.Text(string='Description / Notes')

    def action_activate(self):
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_('Please attach at least one file before activating.'))
        self.document_state = 'active'
        self.message_post(body=_('Document activated.'))

    def action_verify(self):
        self.ensure_one()
        self.write({
            'is_verified': True,
            'verified_by_id': self.env.uid,
            'verified_on': fields.Date.today(),
        })
        self.message_post(body=_('Document verified by %s.') % self.env.user.name)

    def action_archive_document(self):
        self.ensure_one()
        self.document_state = 'archived'
        self.message_post(body=_('Document archived.'))

    def action_create_new_version(self):
        self.ensure_one()
        self.is_latest_version = False
        new_doc = self.copy({
            'version': self.version + 1,
            'previous_version_id': self.id,
            'is_latest_version': True,
            'document_state': 'draft',
            'is_verified': False,
            'verified_by_id': False,
            'verified_on': False,
            'upload_date': fields.Date.today(),
            'attachment_ids': [],
        })
        self.message_post(
            body=_('New version v%d created: %s') % (new_doc.version, new_doc.name),
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Version'),
            'res_model': 'unicore.document',
            'res_id': new_doc.id,
            'view_mode': 'form',
            'target': 'current',
        }
