"""
Face Recognition Controller for Student Attendance
"""
import base64
import json
import logging
from io import BytesIO

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FaceRecognitionController(http.Controller):

    @http.route('/oacis/attendance/face/recognize', type='json', auth='user', methods=['POST'], csrf=False)
    def recognize_face(self, image_data, session_id=None, **kwargs):
        """Recognize face from base64 image data.
        Returns matched student_id, face_registration_id, and confidence.
        """
        if not image_data:
            return {'success': False, 'error': 'No image data provided'}

        try:
            import face_recognition
        except ImportError:
            _logger.error('face_recognition library not installed')
            return {'success': False, 'error': 'Face recognition service unavailable'}

        try:
            # Decode base64 image
            if image_data.startswith('data:image'):
                # Remove data URL prefix
                image_data = image_data.split(',', 1)[1]
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            _logger.error('Image decode failed: %s', e)
            return {'success': False, 'error': 'Invalid image data'}

        try:
            # Load image and get face encodings
            image = face_recognition.load_image_file(BytesIO(image_bytes))
            face_encodings = face_recognition.face_encodings(image)
            if not face_encodings:
                return {'success': False, 'error': 'No face detected in image'}
            if len(face_encodings) > 1:
                return {'success': False, 'error': 'Multiple faces detected. Please ensure only one face is visible.'}

            unknown_encoding = face_encodings[0]

            # Get all active face registrations for the company
            company = request.env.company
            FaceRegistration = request.env['oacis.face.registration'].sudo()
            registrations = FaceRegistration.search([
                ('company_id', '=', company.id),
                ('is_active', '=', True),
                ('face_encoding', '!=', False),
            ])

            if not registrations:
                return {'success': False, 'error': 'No registered faces found'}

            # Compare with known faces
            known_encodings = []
            known_ids = []
            for reg in registrations:
                try:
                    encoding = json.loads(reg.face_encoding)
                    known_encodings.append(encoding)
                    known_ids.append(reg.id)
                except (json.JSONDecodeError, TypeError):
                    continue

            if not known_encodings:
                return {'success': False, 'error': 'No valid face encodings in database'}

            # Calculate face distances
            distances = face_recognition.face_distance(known_encodings, unknown_encoding)
            best_match_idx = distances.argmin()
            best_distance = distances[best_match_idx]
            confidence = 1.0 - best_distance

            # Get the matched registration
            matched_reg_id = known_ids[best_match_idx]
            matched_reg = FaceRegistration.browse(matched_reg_id)

            # Check confidence threshold
            if confidence < matched_reg.confidence_threshold:
                return {
                    'success': False,
                    'error': f'Face not recognized with sufficient confidence (got {confidence:.2f}, need {matched_reg.confidence_threshold:.2f})',
                    'confidence': confidence,
                }

            # Get student from registration
            student = matched_reg.student_id

            # If session_id provided, verify student is enrolled in that session
            if session_id:
                session = request.env['oacis.attendance.session'].browse(int(session_id))
                if session.exists():
                    if student.id not in session.course_offering_id.enrollment_ids.student_id.ids:
                        return {'success': False, 'error': 'Student not enrolled in this session'}

            _logger.info('Face recognized: student=%s, confidence=%.4f', student.display_name, confidence)

            return {
                'success': True,
                'student_id': student.id,
                'student_name': student.display_name,
                'face_registration_id': matched_reg.id,
                'confidence': confidence,
            }

        except Exception as e:
            _logger.exception('Face recognition error')
            return {'success': False, 'error': f'Recognition failed: {str(e)}'}

    @http.route('/oacis/attendance/face/register', type='json', auth='user', methods=['POST'], csrf=False)
    def register_face(self, image_data, student_id=None, **kwargs):
        """Register a new face for a student."""
        if not image_data:
            return {'success': False, 'error': 'No image data provided'}

        try:
            import face_recognition
        except ImportError:
            return {'success': False, 'error': 'Face recognition service unavailable'}

        try:
            if image_data.startswith('data:image'):
                image_data = image_data.split(',', 1)[1]
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            _logger.error('Image decode failed: %s', e)
            return {'success': False, 'error': 'Invalid image data'}

        try:
            image = face_recognition.load_image_file(BytesIO(image_bytes))
            face_encodings = face_recognition.face_encodings(image)
            if not face_encodings:
                return {'success': False, 'error': 'No face detected in image'}
            if len(face_encodings) > 1:
                return {'success': False, 'error': 'Multiple faces detected. Please ensure only one face is visible.'}

            encoding = face_encodings[0].tolist()

            # Create or update face registration
            FaceRegistration = request.env['oacis.face.registration'].sudo()
            if student_id:
                student = request.env['oacis.student'].browse(int(student_id))
                if not student.exists():
                    return {'success': False, 'error': 'Student not found'}
            else:
                # Try to get student from current user
                student = request.env.user.student_id
                if not student:
                    return {'success': False, 'error': 'No student associated with current user'}

            # Deactivate existing registrations
            existing = FaceRegistration.search([
                ('student_id', '=', student.id),
                ('is_active', '=', True),
            ])
            existing.write({'is_active': False})

            # Create new registration
            registration = FaceRegistration.create({
                'student_id': student.id,
                'image': base64.b64encode(image_bytes).decode('utf-8'),
                'face_encoding': json.dumps(encoding),
                'confidence_threshold': 0.6,
            })

            return {
                'success': True,
                'registration_id': registration.id,
                'message': 'Face registered successfully',
            }

        except Exception as e:
            _logger.exception('Face registration error')
            return {'success': False, 'error': f'Registration failed: {str(e)}'}

    @http.route('/oacis/attendance/face/check_session/<int:session_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def check_session_face(self, session_id, image_data, **kwargs):
        """Process face check-in for a specific session."""
        if not image_data:
            return {'success': False, 'error': 'No image data provided'}

        session = request.env['oacis.attendance.session'].browse(session_id)
        if not session.exists():
            return {'success': False, 'error': 'Session not found'}

        if session.session_state != 'open':
            return {'success': False, 'error': 'Session is not open for marking'}

        # Recognize face
        result = self.recognize_face(image_data, session_id=session_id)
        if not result.get('success'):
            return result

        # Get student's attendance record for this session
        student_id = result['student_id']
        record = request.env['oacis.attendance.record'].search([
            ('session_id', '=', session_id),
            ('student_id', '=', student_id),
        ], limit=1)

        if not record:
            return {'success': False, 'error': 'No attendance record found for this student in this session'}

        # Perform face check-in
        try:
            record.action_face_check_in(result['face_registration_id'], result['confidence'])
        except Exception as e:
            return {'success': False, 'error': str(e)}

        return {
            'success': True,
            'student_name': result['student_name'],
            'confidence': result['confidence'],
            'message': f'Check-in successful for {result["student_name"]}',
        }