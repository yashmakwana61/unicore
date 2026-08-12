import base64
import hashlib
import io
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
    _logger.warning('qrcode library not installed. QR code generation will be unavailable.')


class SecureTranscript(models.Model):
    _name = 'unicore.secure.transcript'
    _description = 'Secure Transcript'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'issued_date desc'
    _check_company_auto = True
    _rec_name = 'name'

    student_id = fields.Many2one(
        'unicore.student',
        string='Student',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='student_id.company_id',
        store=True,
    )
    semester_result_ids = fields.Many2many(
        'unicore.semester.result',
        'unicore_transcript_result_rel',
        'transcript_id', 'result_id',
        string='Semester Results',
        domain="[('student_id', '=', student_id), ('is_published', '=', True)]",
    )
    issued_date = fields.Date(
        string='Issued Date',
        default=fields.Date.today,
        tracking=True,
    )
    verification_hash = fields.Char(
        string='Verification Hash',
        readonly=True,
        copy=False,
    )
    qr_code = fields.Binary(
        string='QR Code',
        readonly=True,
        copy=False,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('revoked', 'Revoked'),
    ], string='Status', default='draft', required=True, tracking=True)

    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('student_id', 'issued_date')
    def _compute_name(self):
        for rec in self:
            student_name = rec.student_id.display_name if rec.student_id else 'Unknown'
            date_str = str(rec.issued_date) if rec.issued_date else 'Unknown'
            rec.name = f"Transcript: {student_name} ({date_str})"

    def _generate_hash_payload(self):
        """Build a deterministic JSON payload from the linked semester results."""
        self.ensure_one()
        results_data = []
        for result in self.semester_result_ids.sorted(key=lambda r: r.semester_id.id):
            results_data.append({
                'semester': result.semester_id.display_name,
                'semester_gpa': float(result.semester_gpa),
                'credits_earned': float(result.credits_earned),
                'credits_attempted': float(result.credits_attempted),
                'result_status': result.result_status,
            })
        payload = {
            'student': self.student_id.display_name,
            'student_id_db': self.student_id.id,
            'issued_date': str(self.issued_date),
            'results': results_data,
        }
        return json.dumps(payload, sort_keys=True, separators=(',', ':'))

    def _generate_qr_code(self, verification_url):
        """Generate a QR code image containing the verification URL."""
        if not HAS_QRCODE:
            return False
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(verification_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue())

    def action_issue(self):
        self.ensure_one()
        if not self.semester_result_ids:
            raise ValidationError(_('At least one semester result must be linked before issuing.'))
        payload = self._generate_hash_payload()
        hash_digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        verification_url = f"{base_url}/transcript/verify/{hash_digest}"
        qr_data = self._generate_qr_code(verification_url)
        self.write({
            'state': 'issued',
            'verification_hash': hash_digest,
            'qr_code': qr_data,
            'issued_date': fields.Date.today(),
        })

    def action_revoke(self):
        self.write({'state': 'revoked'})

    @api.constrains('state', 'semester_result_ids')
    def _check_issued_results(self):
        for rec in self:
            if rec.state == 'issued' and not rec.semester_result_ids:
                raise ValidationError(_('An issued transcript must have at least one semester result.'))
