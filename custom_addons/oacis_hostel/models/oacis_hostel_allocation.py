"""
Oacis Hostel Allocation Model
Assignment of a student to a hostel room for
an academic year. Tracks check-in, check-out,
hostel fees and room condition.
"""

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OacisHostelAllocation(models.Model):
    _name = 'oacis.hostel.allocation'
    _description = 'Hostel Room Allocation'
    _inherit = ['oacis.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'academic_year_id desc, student_id'
    _check_company_auto = True
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['allocation_number', 'student_id.display_name'],
    )

    @api.depends('allocation_number', 'student_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            code = (
                rec.allocation_number
                if rec.allocation_number and rec.allocation_number != '/'
                else ''
            )
            student_name = (
                rec.student_id.display_name if rec.student_id else ''
            )
            if code and student_name:
                rec.display_name = '%s - %s' % (code, student_name)
            else:
                rec.display_name = student_name or code

    allocation_number = fields.Char(
        string='Allocation Number',
        readonly=True,
        copy=False,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    # --- STUDENT & ROOM ---

    student_id = fields.Many2one(
        comodel_name='oacis.student',
        string='Student',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('company_id','=',company_id),"
               "('student_state','in',"
               "['enrolled','active'])]",
    )
    room_id = fields.Many2one(
        comodel_name='oacis.hostel.room',
        string='Room',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('company_id','=',company_id),"
               "('room_state','in',"
               "['available','partial'])]",
    )
    block_id = fields.Many2one(
        comodel_name='oacis.hostel.block',
        string='Block',
        related='room_id.block_id',
        store=True,
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
        tracking=True,
    )

    # --- DATES ---

    allocation_date = fields.Date(
        string='Allocation Date',
        required=True,
        default=fields.Date.today,
        readonly=True,
    )
    expected_checkin = fields.Date(
        string='Expected Check-In',
        tracking=True,
    )
    actual_checkin = fields.Date(
        string='Actual Check-In',
        readonly=True,
        tracking=True,
    )
    expected_checkout = fields.Date(
        string='Expected Check-Out',
        tracking=True,
    )
    actual_checkout = fields.Date(
        string='Actual Check-Out',
        readonly=True,
        tracking=True,
    )

    # --- FEES ---

    monthly_rent = fields.Monetary(
        string='Monthly Rent',
        related='room_id.monthly_rent',
        store=True,
        currency_field='currency_id',
        readonly=True,
    )
    security_deposit = fields.Monetary(
        string='Security Deposit',
        related='room_id.security_deposit',
        store=True,
        currency_field='currency_id',
        readonly=True,
    )
    security_deposit_paid = fields.Boolean(
        string='Security Deposit Paid',
        default=False,
        tracking=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
        store=True,
    )
    total_hostel_fee = fields.Monetary(
        string='Total Hostel Fee (Semester)',
        compute='_compute_total_fee',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('monthly_rent',
                 'expected_checkin',
                 'expected_checkout')
    def _compute_total_fee(self):
        for rec in self:
            if (rec.expected_checkin
                    and rec.expected_checkout):
                months = max(
                    1,
                    (
                        (rec.expected_checkout.year
                         - rec.expected_checkin.year)
                        * 12
                        + rec.expected_checkout.month
                        - rec.expected_checkin.month
                        + 1
                    ),
                )
                rec.total_hostel_fee = (
                    rec.monthly_rent * months
                )
            else:
                rec.total_hostel_fee = (
                    rec.monthly_rent * 5
                )  # default 5 months

    # --- CONDITION ---

    condition_on_checkin = fields.Selection(
        string='Room Condition (Check-In)',
        selection=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
        ],
    )
    condition_on_checkout = fields.Selection(
        string='Room Condition (Check-Out)',
        selection=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
            ('damaged', 'Damaged'),
        ],
    )
    damage_charges = fields.Monetary(
        string='Damage Charges',
        default=0.0,
        currency_field='currency_id',
    )
    security_deposit_refund = fields.Monetary(
        string='Security Deposit Refund',
        compute='_compute_refund',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('security_deposit',
                 'damage_charges',
                 'security_deposit_paid')
    def _compute_refund(self):
        for rec in self:
            if rec.security_deposit_paid:
                rec.security_deposit_refund = max(
                    0.0,
                    rec.security_deposit
                    - rec.damage_charges,
                )
            else:
                rec.security_deposit_refund = 0.0

    # --- NOTES ---

    checkin_notes = fields.Text(
        string='Check-In Notes',
    )
    checkout_notes = fields.Text(
        string='Check-Out Notes',
    )
    special_requirements = fields.Text(
        string='Special Requirements',
    )

    # --- STATUS ---

    allocation_state = fields.Selection(
        string='Status',
        required=True,
        default='allocated',
        tracking=True,
        selection=[
            ('allocated', 'Allocated'),
            ('checked_in', 'Checked In'),
            ('checked_out', 'Checked Out'),
            ('cancelled', 'Cancelled'),
            ('no_show', 'No Show'),
        ],
    )

    _sql_constraints = [
        (
            'unique_allocation_number',
            'UNIQUE(allocation_number)',
            'Allocation number must be unique.',
        ),
        (
            'unique_student_academic_year',
            'UNIQUE(student_id, academic_year_id)',
            'Student already has a hostel allocation '
            'for this academic year.',
        ),
    ]

    @api.constrains('student_id', 'room_id')
    def _check_gender_compatibility(self):
        for rec in self:
            block = rec.room_id.block_id
            student = rec.student_id
            if block.gender_type == 'mixed':
                continue
            if (block.gender_type == 'male'
                    and student.gender == 'female'):
                raise ValidationError(
                    _('Female students cannot be '
                      'allocated to a Boys hostel.'),
                )
            if (block.gender_type == 'female'
                    and student.gender == 'male'):
                raise ValidationError(
                    _('Male students cannot be '
                      'allocated to a Girls hostel.'),
                )

    @api.constrains('room_id')
    def _check_room_capacity(self):
        for rec in self:
            room = rec.room_id
            if room.is_full:
                raise ValidationError(
                    _('Room %s is already at full '
                      'capacity.')
                    % room.room_number,
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('allocation_number'):
                vals['allocation_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'oacis.hostel.allocation',
                    ) or '/'
                )
        return super().create(vals_list)

    def action_checkin(self):
        self.ensure_one()
        if self.allocation_state != 'allocated':
            raise UserError(
                _('Only allocated rooms can be '
                  'checked in.'),
            )
        self.write({
            'allocation_state': 'checked_in',
            'actual_checkin': date.today(),
        })
        self._update_room_state()
        self.message_post(
            body=_('%s checked in to Room %s, '
                   'Block %s on %s.')
                 % (
                     self.student_id.display_name,
                     self.room_id.room_number,
                     self.block_id.name,
                     date.today(),
                 ),
        )

    def action_checkout(self):
        self.ensure_one()
        if self.allocation_state != 'checked_in':
            raise UserError(
                _('Only checked-in students can '
                  'check out.'),
            )
        self.write({
            'allocation_state': 'checked_out',
            'actual_checkout': date.today(),
        })
        self._update_room_state()
        self.message_post(
            body=_('%s checked out from Room %s on %s. '
                   'Security Refund: %s')
                 % (
                     self.student_id.display_name,
                     self.room_id.room_number,
                     date.today(),
                     self.security_deposit_refund,
                 ),
        )

    def action_cancel(self):
        self.ensure_one()
        if self.allocation_state == 'checked_in':
            raise UserError(
                _('Cannot cancel a checked-in '
                  'allocation. Please check out first.'),
            )
        self.write({
            'allocation_state': 'cancelled',
        })
        self._update_room_state()
        self.message_post(
            body=_('Allocation cancelled.'),
        )

    def _update_room_state(self):
        """Sync room state based on current occupancy."""
        self.ensure_one()
        room = self.room_id
        if room.is_full:
            room.room_state = 'occupied'
        elif room.current_occupancy > 0:
            room.room_state = 'partial'
        else:
            room.room_state = 'available'
