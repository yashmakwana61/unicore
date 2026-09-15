"""
Face Registration Model for Student Attendance
"""
import base64
import json
import logging
from io import BytesIO

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OacisFaceRegistration(models.Model):
    """Face registration for student biometric attendance"""
    _name = 'oacis.face.registration'
    _description = 'Student Face Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'student_id, create_date desc'

    student_id = fields.Many2one(
        'oacis.student',
        string='Student',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='student_id.partner_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    image = fields.Binary(
        string='Face Image',
        attachment=True,
        help='Clear face photo for recognition',
    )
    image_medium = fields.Binary(
        string='Medium Image',
        compute='_compute_image_medium',
        store=True,
    )
    face_encoding = fields.Text(
        string='Face Encoding',
        help='JSON-encoded face embedding vector (128-dim)',
        groups='oacis_base.group_oacis_admin',
    )
    is_active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
    )
    registration_date = fields.Date(
        string='Registration Date',
        default=fields.Date.context_today,
        required=True,
    )
    last_used = fields.Datetime(
        string='Last Used',
        readonly=True,
    )
    usage_count = fields.Integer(
        string='Usage Count',
        default=0,
        readonly=True,
    )
    confidence_threshold = fields.Float(
        string='Confidence Threshold',
        default=0.6,
        help='Minimum face match confidence (0.0-1.0). Lower = more permissive.',
    )
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_active_student', 'unique(student_id, is_active)',
         'A student can only have one active face registration at a time.'),
    ]

    @api.depends('image')
    def _compute_image_medium(self):
        for rec in self:
            if rec.image:
                rec.image_medium = rec.image
            else:
                rec.image_medium = False

    @api.constrains('face_encoding')
    def _check_face_encoding(self):
        for rec in self:
            if rec.face_encoding:
                try:
                    encoding = json.loads(rec.face_encoding)
                    if not isinstance(encoding, list) or len(encoding) != 128:
                        raise ValidationError(_('Face encoding must be a 128-dimensional vector.'))
                    for val in encoding:
                        if not isinstance(val, (int, float)):
                            raise ValidationError(_('Face encoding values must be numbers.'))
                except json.JSONDecodeError:
                    raise ValidationError(_('Face encoding must be valid JSON.'))

    def _extract_face_encoding(self, image_data):
        """Extract face encoding from image binary data.
        Returns list of 128 floats or None if no face found."""
        try:
            import face_recognition
        except ImportError:
            _logger.error('face_recognition library not installed')
            return None

        try:
            image = face_recognition.load_image_file(BytesIO(base64.b64decode(image_data)))
            encodings = face_recognition.face_encodings(image)
            if encodings:
                return encodings[0].tolist()
        except Exception as e:
            _logger.error('Face encoding extraction failed: %s', e)
        return None

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('image') and not vals.get('face_encoding'):
                encoding = self._extract_face_encoding(vals['image'])
                if encoding:
                    vals['face_encoding'] = json.dumps(encoding)
                else:
                    raise ValidationError(_('No face detected in the uploaded image. Please try a clearer photo.'))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('image') and 'face_encoding' not in vals:
            for rec in self:
                encoding = self._extract_face_encoding(vals['image'])
                if encoding:
                    vals['face_encoding'] = json.dumps(encoding)
                else:
                    raise ValidationError(_('No face detected in the uploaded image. Please try a clearer photo.'))
        return super().write(vals)

    def action_deactivate(self):
        self.write({'is_active': False})

    def action_reactivate(self):
        self.write({'is_active': True})

    def record_usage(self):
        """Record a successful face recognition usage"""
        self.write({
            'last_used': fields.Datetime.now(),
            'usage_count': self.usage_count + 1,
        })