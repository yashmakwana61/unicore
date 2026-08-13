"""
Extends oacis.notification.template to add
trigger events for student leave request workflows.
"""
from odoo import models


class OacisNotificationTemplateExtension(models.Model):
    """Add leave request trigger events to the
    notification template model."""
    _inherit = 'oacis.notification.template'

    def _selection_trigger_event(self):
        """Extend the trigger_event selection with
        leave request events."""
        # Get parent selection values
        current_selection = super()._selection_trigger_event(
        ) if hasattr(
            models.Model, '_selection_trigger_event',
        ) else []

        # If super() is not available or returns empty,
        # we need the base values
        if not current_selection:
            current_selection = [
                ('fee_due', 'Fee Due Reminder'),
                ('fee_overdue', 'Fee Overdue Alert'),
                ('fee_paid', 'Fee Payment Confirmation'),
                ('attendance_shortage',
                 'Attendance Shortage Alert'),
                ('attendance_warning',
                 'Attendance Warning'),
                ('exam_reminder', 'Exam Reminder'),
                ('exam_hall_ticket',
                 'Hall Ticket Available'),
                ('result_published',
                 'Result Published'),
                ('enrollment_confirmed',
                 'Enrollment Confirmed'),
                ('scholarship_approved',
                 'Scholarship Approved'),
                ('scholarship_awarded',
                 'Scholarship Award Disbursed'),
                ('welcome', 'Welcome / Admission'),
                ('custom', 'Custom / Manual'),
            ]

        # Add leave request events
        current_selection.extend([
            ('leave_request_approved',
             'Leave Request Approved'),
            ('leave_request_rejected',
             'Leave Request Rejected'),
        ])
        return current_selection
