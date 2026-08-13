"""
Oacis Student Leave Request Model
Provides a student/guardian-initiated leave request
workflow distinct from the registrar-side
"Place on Leave" button. On approval, triggers the
existing action_place_on_leave on oacis.student.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OacisStudentLeaveRequest(models.Model):
    _name = 'oacis.student.leave.request'
    _description = 'Student Leave Request'
    _inherit = ['oacis.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'date_from desc, id desc'
    _check_company_auto = True
    _rec_name = 'name'

    # --- IDENTITY ---

    name = fields.Char(
        string='Request Reference',
        readonly=True,
        copy=False,
        tracking=True,
    )

    # --- REQUEST DETAILS ---

    student_id = fields.Many2one(
        comodel_name='oacis.student',
        string='Student',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    guardian_id = fields.Many2one(
        comodel_name='oacis.guardian',
        string='Submitted By (Guardian)',
        ondelete='restrict',
        tracking=True,
        help='Set if this request was submitted by a guardian',
    )
    submitted_by = fields.Selection(
        selection=[
            ('student', 'Student'),
            ('guardian', 'Guardian'),
        ],
        string='Submitted By',
        required=True,
        default='student',
        readonly=True,
        tracking=True,
    )
    reason = fields.Text(
        string='Reason for Leave',
        required=True,
        tracking=True,
    )
    date_from = fields.Date(
        string='Leave Start Date',
        required=True,
        tracking=True,
    )
    date_to = fields.Date(
        string='Leave End Date',
        required=True,
        tracking=True,
    )
    leave_duration = fields.Integer(
        string='Duration (Days)',
        compute='_compute_leave_duration',
        store=False,
    )

    # --- SUPPORTING DOCUMENT ---

    supporting_document = fields.Binary(
        string='Supporting Document',
        attachment=True,
    )
    supporting_document_name = fields.Char(
        string='Document Name',
    )

    # --- STATE ---

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        readonly=True,
        tracking=True,
    )

    # --- APPROVAL ---

    approver_id = fields.Many2one(
        comodel_name='res.users',
        string='Approved By',
        readonly=True,
        copy=False,
    )
    approval_date = fields.Date(
        string='Approval Date',
        readonly=True,
        copy=False,
    )
    approval_notes = fields.Text(
        string='Approval / Rejection Notes',
        tracking=True,
    )

    # --- SYSTEM ---

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Submitted By User',
        default=lambda self: self.env.user,
        readonly=True,
        copy=False,
    )

    # --- RELATED / HELPERS ---

    student_name = fields.Char(
        string='Student Name',
        related='student_id.display_name',
        readonly=True,
        store=False,
    )
    student_number = fields.Char(
        string='Student ID',
        related='student_id.student_id_number',
        readonly=True,
        store=False,
    )
    guardian_name = fields.Char(
        string='Guardian Name',
        related='guardian_id.display_name',
        readonly=True,
        store=False,
    )

    # --- CONSTRAINTS ---

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to:
                if record.date_to < record.date_from:
                    raise ValidationError(_(
                        'Leave end date cannot be before '
                        'start date.',
                    ))

    @api.constrains('student_id', 'state')
    def _check_already_on_leave(self):
        for record in self:
            if (record.student_id
                    and record.student_id.student_state
                    == 'on_leave'
                    and record.state in ('draft', 'submitted')):
                raise ValidationError(_(
                    'Student is already on leave. Cannot '
                    'submit a new leave request while '
                    'the student is currently on leave.',
                ))

    # --- COMPUTES ---

    @api.depends('date_from', 'date_to')
    def _compute_leave_duration(self):
        for record in self:
            if record.date_from and record.date_to:
                delta = (record.date_to - record.date_from)
                record.leave_duration = delta.days + 1
            else:
                record.leave_duration = 0

    # --- LIFECYCLE ---

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = (
                    self.env['ir.sequence']
                    .next_by_code(
                        'oacis.student.leave.request',
                    )
                    or '/'
                )
        return super().create(vals_list)

    # --- STATE TRANSITIONS ---

    def action_submit(self):
        """Draft → Submitted. Notifies approvers."""
        for record in self:
            if record.state != 'draft':
                raise UserError(_(
                    'Only draft requests can be '
                    'submitted.',
                ))
            if not record.reason:
                raise UserError(_(
                    'Please provide a reason for '
                    'the leave request.',
                ))
            if not record.date_from or not record.date_to:
                raise UserError(_(
                    'Please specify both start and '
                    'end dates.',
                ))
            record.write({
                'state': 'submitted',
                'submitted_by': (
                    'guardian' if record.guardian_id
                    else 'student'
                ),
            })
            record.message_post(
                body=_('Leave request submitted by %s.') % (
                    record.guardian_name
                    if record.guardian_id
                    else record.student_name
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            record._notify_approvers()
            _logger.info(
                'Leave request %s submitted for '
                'student %s.',
                record.name,
                record.student_id.student_id_number,
            )

    def action_approve(self):
        """Submitted → Approved. Triggers Place on
        Leave on the student record.

        Calls the existing action_place_on_leave()
        to honour the integration point, then also
        performs the state write so the transition
        happens without requiring the wizard UI.
        """
        for record in self:
            if record.state != 'submitted':
                raise UserError(_(
                    'Only submitted requests can be '
                    'approved.',
                ))
            student = record.student_id
            if student.student_state == 'on_leave':
                raise UserError(_(
                    'Student is already on leave.',
                ))

            # Invoke the existing Place on Leave
            # action (returns a wizard action dict;
            # kept here for integration completeness).
            student.action_place_on_leave()

            # Perform the actual state transition
            # using the leave request's reason and
            # dates — mirrors what the status wizard
            # action_confirm does.
            old_state = student.student_state
            student.write({
                'student_state': 'on_leave',
                'status_change_date': (
                    record.date_from or fields.Date.today()
                ),
                'status_change_reason': record.reason,
            })
            student._post_status_message(
                old_state, 'on_leave', record.reason,
            )

            record.write({
                'state': 'approved',
                'approver_id': self.env.user.id,
                'approval_date': fields.Date.today(),
                'approval_notes': record.approval_notes or '',
            })

            # Notify student and guardian
            record._notify_request_decision('approved')
            _logger.info(
                'Leave request %s approved for '
                'student %s.',
                record.name,
                student.student_id_number,
            )

    def action_reject(self):
        """Submitted → Rejected. Notifies student/guardian."""
        for record in self:
            if record.state != 'submitted':
                raise UserError(_(
                    'Only submitted requests can be '
                    'rejected.',
                ))
            record.write({
                'state': 'rejected',
                'approver_id': self.env.user.id,
                'approval_date': fields.Date.today(),
                'approval_notes': record.approval_notes or '',
            })
            record.message_post(
                body=_(
                    'Leave request rejected by %s. '
                    'Notes: %s',
                ) % (
                    self.env.user.name,
                    record.approval_notes or '(none)',
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            record._notify_request_decision('rejected')
            _logger.info(
                'Leave request %s rejected for '
                'student %s.',
                record.name,
                record.student_id.student_id_number,
            )

    def action_resubmit(self):
        """Rejected → Draft (for re-submission)."""
        for record in self:
            if record.state != 'rejected':
                raise UserError(_(
                    'Only rejected requests can be '
                    'resubmitted.',
                ))
            record.write({
                'state': 'draft',
                'approver_id': False,
                'approval_date': False,
                'approval_notes': '',
            })

    def action_cancel(self):
        """Draft/Submitted → Cancelled."""
        for record in self:
            if record.state not in ('draft', 'submitted'):
                raise UserError(_(
                    'Only draft or submitted requests '
                    'can be cancelled.',
                ))
            record.write({'state': 'cancelled'})
            record.message_post(
                body=_('Leave request cancelled.'),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    # --- NOTIFICATION HELPERS ---

    def _notify_approvers(self):
        """Assign a mail activity for the registrar
        group to review this request."""
        self.ensure_one()
        # Find a registrar user to assign the activity
        RegistrarGroup = self.env.ref(
            'oacis_base.group_oacis_registrar',
            raise_if_not_found=False,
        )
        if not RegistrarGroup or not RegistrarGroup.users:
            _logger.warning(
                'No registrar users found for '
                'activity assignment on %s.',
                self.name,
            )
            return

        # Pick the first available registrar
        approver = RegistrarGroup.users[0]
        self.activity_schedule(
            activity_type_id=self.env.ref(
                'mail.mail_activity_data_todo',
            ).id,
            summary=_('Review Leave Request: %s') % (
                self.name,
            ),
            user_id=approver.id,
            note=_(
                'Leave request for student %s '
                '(%s) from %s to %s. Reason: %s',
            ) % (
                self.student_name,
                self.student_number or '',
                self.date_from,
                self.date_to,
                self.reason,
            ),
        )

    def _notify_request_decision(self, decision):
        """Send notification to student and guardian
        when the request is approved or rejected."""
        self.ensure_one()
        Engine = self.env['oacis.notification.engine']
        variables = {
            'student_name': self.student_name,
            'student_id': self.student_number or '',
            'date_from': str(self.date_from or ''),
            'date_to': str(self.date_to or ''),
            'reason': self.reason or '',
            'approver_name': (
                self.approver_id.name or ''
            ),
            'approval_notes': (
                self.approval_notes or ''
            ),
            'institution_name': self.company_id.name,
            'request_reference': self.name or '',
        }

        trigger_event = (
            'leave_request_approved'
            if decision == 'approved'
            else 'leave_request_rejected'
        )

        # Notify the student
        try:
            Engine.send_to_student(
                student=self.student_id,
                trigger_event=trigger_event,
                variables=variables,
            )
        except Exception as e:
            _logger.warning(
                'Failed to notify student %s '
                'on leave request %s: %s',
                self.student_name, self.name, str(e),
            )

        # Notify the guardian if one is linked
        if self.guardian_id:
            try:
                Engine.send_to_guardian(
                    guardian=self.guardian_id,
                    trigger_event=trigger_event,
                    variables=variables,
                    student=self.student_id,
                )
            except Exception as e:
                _logger.warning(
                    'Failed to notify guardian %s '
                    'on leave request %s: %s',
                    self.guardian_name,
                    self.name,
                    str(e),
                )

    # --- ACTIONS ---

    def action_view_student(self):
        """Open the related student record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student'),
            'res_model': 'oacis.student',
            'res_id': self.student_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_guardian(self):
        """Open the related guardian record."""
        self.ensure_one()
        if not self.guardian_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Guardian'),
            'res_model': 'oacis.guardian',
            'res_id': self.guardian_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
