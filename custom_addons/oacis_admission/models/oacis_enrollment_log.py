"""
Oacis Enrollment Log Model
Immutable, append-only audit trail of every
enrollment state change. Created automatically by
oacis.enrollment action methods — never created
or edited directly by users. Required for
accreditation and compliance record-keeping.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OacisEnrollmentLog(models.Model):
    _name = 'oacis.enrollment.log'
    _description = 'Enrollment Audit Log'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['student_id.display_name', 'course_offering_id.display_name',
                 'action'],
    )

    @api.depends('student_id.display_name', 'course_offering_id.display_name',
                 'action')
    def _compute_display_name(self):
        action_labels = dict(
            self._fields['action'].selection,
        ) if 'action' in self._fields else {}
        for rec in self:
            student_name = (
                rec.student_id.display_name if rec.student_id else ''
            )
            offering_name = (
                rec.course_offering_id.display_name
                if rec.course_offering_id else ''
            )
            action_label = action_labels.get(rec.action, rec.action or '')
            if action_label:
                rec.display_name = '%s - %s (%s)' % (
                    student_name, offering_name, action_label,
                )
            else:
                rec.display_name = '%s - %s' % (
                    student_name, offering_name,
                )
    _order = 'action_date desc'

    enrollment_id = fields.Many2one(
        comodel_name='oacis.enrollment',
        string='Enrollment',
        required=True,
        ondelete='cascade',
        index=True,
    )

    student_id = fields.Many2one(
        comodel_name='oacis.student',
        string='Student',
        required=True,
        ondelete='cascade',
        index=True,
    )

    course_offering_id = fields.Many2one(
        comodel_name='oacis.course.offering',
        string='Course Offering',
        required=True,
        ondelete='cascade',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='course_offering_id.company_id',
        store=True,
        readonly=True,
    )

    action = fields.Selection(
        string='Action',
        required=True,
        selection=[
            ('registered', 'Registered'),
            ('dropped', 'Dropped'),
            ('withdrawn', 'Withdrawn'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
    )

    action_date = fields.Datetime(
        string='Action Date',
        required=True,
    )

    performed_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Performed By',
        required=True,
    )

    notes = fields.Text(string='Notes')

    def write(self, vals):
        raise UserError(
            _('Enrollment log entries are immutable and cannot be edited. '
              'This is an audit compliance requirement.'),
        )

    def unlink(self):
        raise UserError(
            _('Enrollment log entries are immutable and cannot be deleted. '
              'This is an audit compliance requirement.'),
        )
