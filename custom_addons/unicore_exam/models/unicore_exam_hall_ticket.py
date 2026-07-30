"""
UniCore Exam Hall Ticket Model
Per-student authorization to sit a specific exam.
Generated in bulk by the exam schedule's
action_generate_hall_tickets() method.
Includes attendance eligibility check result.
Approved hall tickets feed into the seating plan.
Each ticket has a unique auto-generated ticket number.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreExamHallTicket(models.Model):
    _name = 'unicore.exam.hall.ticket'
    _description = 'Exam Hall Ticket'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'exam_schedule_id, student_id'
    _check_company_auto = True
    _rec_name = 'ticket_number'

    ticket_number = fields.Char(
        string='Ticket Number',
        readonly=True,
        copy=False,
        index=True,
        help='Auto-generated unique ticket identifier',
    )

    exam_schedule_id = fields.Many2one(
        comodel_name='unicore.exam.schedule',
        string='Exam',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )

    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )

    enrollment_id = fields.Many2one(
        comodel_name='unicore.enrollment',
        string='Enrollment',
        ondelete='set null',
    )

    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        related='exam_schedule_id.course_id',
        store=True,
        readonly=True,
    )

    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        related='exam_schedule_id.semester_id',
        store=True,
        readonly=True,
    )

    exam_date = fields.Date(
        string='Exam Date',
        related='exam_schedule_id.exam_date',
        store=True,
        readonly=True,
    )

    exam_type = fields.Selection(
        string='Exam Type',
        related='exam_schedule_id.exam_type',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='exam_schedule_id.company_id',
        store=True,
        readonly=True,
    )

    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        related='exam_schedule_id.campus_id',
        store=True,
        readonly=True,
    )

    eligibility_status = fields.Selection(
        string='Eligibility',
        required=True,
        default='eligible',
        tracking=True,
        selection=[
            ('eligible', 'Eligible'),
            ('ineligible', 'Ineligible — Attendance'),
            ('ineligible_fees', 'Ineligible — Fees Due'),
            ('override', 'Override Approved'),
        ],
    )

    eligibility_note = fields.Text(
        string='Eligibility Note',
        readonly=True,
    )

    ticket_state = fields.Selection(
        string='Ticket Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('blocked', 'Blocked'),
            ('used', 'Used'),
            ('cancelled', 'Cancelled'),
        ],
    )

    seating_id = fields.Many2one(
        comodel_name='unicore.exam.seating',
        string='Seat Assignment',
        readonly=True,
        copy=False,
    )

    _unique_ticket_number = models.Constraint(
        'UNIQUE(ticket_number)',
        'Hall ticket number must be globally unique.',
    )

    _unique_student_exam = models.Constraint(
        'UNIQUE(exam_schedule_id, student_id)',
        'This student already has a hall ticket for this exam.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('ticket_number'):
                vals['ticket_number'] = (
                    self.env['ir.sequence'].next_by_code('unicore.exam.hall.ticket') or '/'
                )
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            if rec.ticket_state == 'draft':
                if rec.eligibility_status == 'ineligible' and not self.env.context.get('force_approve'):
                    raise UserError(
                        _('Student "%s" is ineligible: %s\n\n'
                          'Use Override Approval to proceed despite ineligibility.')
                        % (rec.student_id.display_name, rec.eligibility_note)
                    )
                rec.ticket_state = 'approved'
                rec.message_post(body=_('Hall ticket approved.'))

    def action_override_approve(self):
        for rec in self:
            rec.write({
                'ticket_state': 'approved',
                'eligibility_status': 'override',
                'eligibility_note': (
                    (rec.eligibility_note or '')
                    + _('\nOverride approved by %s.') % self.env.user.name
                ),
            })
            rec.message_post(
                body=_('Hall ticket override-approved by %s despite ineligibility.')
                % self.env.user.name
            )

    def action_block(self):
        for rec in self:
            rec.ticket_state = 'blocked'
            rec.message_post(body=_('Hall ticket blocked.'))

    def action_cancel(self):
        for rec in self:
            rec.ticket_state = 'cancelled'
            rec.message_post(body=_('Hall ticket cancelled.'))

    def action_mark_used(self):
        for rec in self:
            if rec.ticket_state != 'approved':
                raise UserError(_('Only approved tickets can be marked as used.'))
            rec.ticket_state = 'used'

    def action_approve_all_eligible(self):
        eligible_draft = self.filtered(
            lambda t: t.ticket_state == 'draft' and t.eligibility_status == 'eligible'
        )
        for rec in eligible_draft:
            rec.ticket_state = 'approved'
        self.exam_schedule_id[:1].message_post(
            body=_('%d eligible tickets approved in batch.') % len(eligible_draft)
        )
