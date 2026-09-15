"""
Face Check-in Wizard for Student Attendance
"""
import logging
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OacisFaceCheckInWizard(models.TransientModel):
    """Wizard for student face check-in during session"""
    _name = 'oacis.face.checkin.wizard'
    _description = 'Student Face Check-in'

    session_id = fields.Many2one(
        'oacis.attendance.session',
        string='Session',
        required=True,
        ondelete='cascade',
    )
    student_id = fields.Many2one(
        'oacis.student',
        string='Student',
        readonly=True,
    )
    course_offering_id = fields.Many2one(
        'oacis.course.offering',
        related='session_id.course_offering_id',
        readonly=True,
    )
    session_date = fields.Date(
        related='session_id.session_date',
        readonly=True,
    )
    time_slot_id = fields.Many2one(
        'oacis.time.slot',
        related='session_id.time_slot_id',
        readonly=True,
    )
    room_id = fields.Many2one(
        'oacis.room',
        related='session_id.room_id',
        readonly=True,
    )

    # Face check-in fields
    face_image = fields.Binary(
        string='Captured Image',
        attachment=False,
        help='Base64 encoded image from camera',
    )
    face_registration_id = fields.Many2one(
        'oacis.face.registration',
        string='Matched Face Registration',
        readonly=True,
    )
    matched_student_id = fields.Many2one(
        'oacis.student',
        string='Recognized Student',
        readonly=True,
    )
    confidence = fields.Float(
        string='Confidence Score',
        readonly=True,
        digits=(5, 4),
    )
    recognition_result = fields.Text(
        string='Recognition Result',
        readonly=True,
    )

    # Status
    state = fields.Selection([
        ('ready', 'Ready to Scan'),
        ('processing', 'Processing...'),
        ('success', 'Recognized'),
        ('error', 'Error'),
    ], string='Status', default='ready')

    def action_reset(self):
        """Reset wizard to ready state"""
        self.write({
            'state': 'ready',
            'face_image': False,
            'face_registration_id': False,
            'matched_student_id': False,
            'confidence': 0.0,
            'recognition_result': False,
            'student_id': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_recognize(self):
        """Call face recognition API"""
        self.ensure_one()
        if not self.face_image:
            raise UserError(_('Please capture an image first.'))

        # Call recognition endpoint
        url = '/oacis/attendance/face/check_session/%d' % self.session_id.id
        result = self.env['ir.http'].sudo()._dispatch_request(
            'POST', url, json={'image_data': self.face_image.decode('utf-8') if isinstance(self.face_image, bytes) else self.face_image}
        )
        # Since we can't easily call internal HTTP, we'll call the controller method directly
        controller = self.env['ir.http'].sudo().get_controller('face_recognition')
        # Better: call the controller method via the registry
        from oacis_attendance.controllers.face_recognition_controller import FaceRecognitionController
        ctrl = FaceRecognitionController()
        result = ctrl.check_session_face(self.session_id.id, self.face_image)

        if result.get('success'):
            self.write({
                'state': 'success',
                'matched_student_id': result.get('student_id'),
                'confidence': result.get('confidence'),
                'recognition_result': json.dumps(result),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Face Recognized'),
                    'message': _('Recognized: %s (Confidence: %.2f%%)') % (result.get('student_name', ''), result.get('confidence', 0) * 100),
                    'type': 'success',
                },
            }
        else:
            self.write({
                'state': 'error',
                'recognition_result': json.dumps(result),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Recognition Failed'),
                    'message': result.get('error', _('Unknown error')),
                    'type': 'danger',
                },
            }

    def action_confirm_check_in(self):
        """Confirm the face check-in and mark attendance"""
        self.ensure_one()
        if self.state != 'success':
            raise UserError(_('Face not recognized yet. Please scan first.'))

        result = json.loads(self.recognition_result) if self.recognition_result else {}
        if not result.get('success'):
            raise UserError(_('Invalid recognition result.'))

        # Get the attendance record
        record = self.env['oacis.attendance.record'].search([
            ('session_id', '=', self.session_id.id),
            ('student_id', '=', result['student_id']),
        ], limit=1)

        if not record:
            raise UserError(_('No attendance record found for this student in this session.'))

        if record.face_check_in:
            raise UserError(_('This student has already checked in via face recognition.'))

        # Perform the check-in
        record.action_face_check_in(result['face_registration_id'], result['confidence'])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Check-in Complete'),
                'message': _('Attendance marked as Present for %s') % result.get('student_name', ''),
                'type': 'success',
                'sticky': True,
            },
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'oacis.attendance.session':
            session = self.env['oacis.attendance.session'].browse(self.env.context.get('active_id'))
            if session:
                res['session_id'] = session.id
        return res