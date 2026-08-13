"""
Oacis Transport Pass Model
A student's subscription to a transport route
for a specific semester. Carries the pass number,
boarding stop, fee and payment status.
"""

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OacisTransportPass(models.Model):
    _name = 'oacis.transport.pass'
    _description = 'Student Transport Pass'
    _inherit = ['oacis.mixin', 'mail.thread']
    _order = 'academic_year_id desc, student_id'
    _check_company_auto = True
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['pass_number', 'student_id.display_name'],
    )

    @api.depends('pass_number', 'student_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            code = (
                rec.pass_number
                if rec.pass_number and rec.pass_number != '/'
                else ''
            )
            student_name = (
                rec.student_id.display_name if rec.student_id else ''
            )
            if code and student_name:
                rec.display_name = '%s - %s' % (code, student_name)
            else:
                rec.display_name = student_name or code

    pass_number = fields.Char(
        string='Pass Number',
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

    # --- STUDENT & ROUTE ---

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
    route_id = fields.Many2one(
        comodel_name='oacis.transport.route',
        string='Route',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('route_state','=','active'),"
               "('company_id','=',company_id)]",
    )
    vehicle_id = fields.Many2one(
        comodel_name='oacis.transport.vehicle',
        string='Vehicle',
        related='route_id.vehicle_id',
        store=True,
        readonly=True,
    )
    boarding_stop_id = fields.Many2one(
        comodel_name='oacis.transport.stop',
        string='Boarding Stop',
        ondelete='set null',
        domain="[('route_id','=',route_id),"
               "('is_active','=',True)]",
        help='Stop where student boards the bus',
    )

    # --- ACADEMIC PERIOD ---

    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
        tracking=True,
    )
    semester_id = fields.Many2one(
        comodel_name='oacis.semester',
        string='Semester',
        ondelete='set null',
        domain="[('academic_year_id','=',"
               "academic_year_id)]",
        tracking=True,
    )
    valid_from = fields.Date(
        string='Valid From',
        required=True,
        default=fields.Date.today,
    )
    valid_until = fields.Date(
        string='Valid Until',
        required=True,
        tracking=True,
    )
    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired',
        search='_search_is_expired',
        store=False,
    )

    @api.depends('valid_until')
    def _compute_is_expired(self):
        today = date.today()
        for rec in self:
            rec.is_expired = (
                bool(rec.valid_until)
                and rec.valid_until < today
            )

    def _search_is_expired(self, operator, value):
        today = date.today()
        if (operator == '=' and value) or (operator in ('!=', '<>') and not value):
            return [('valid_until', '<', today), ('valid_until', '!=', False)]
        return ['|', ('valid_until', '>=', today), ('valid_until', '=', False)]

    # --- FEES ---

    transport_fee = fields.Monetary(
        string='Transport Fee',
        currency_field='currency_id',
        tracking=True,
        help='Fee charged for this pass',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
        store=True,
    )
    fee_paid = fields.Boolean(
        string='Fee Paid',
        default=False,
        tracking=True,
    )
    fee_paid_date = fields.Date(
        string='Fee Paid On',
        readonly=True,
    )
    payment_reference = fields.Char(
        string='Payment Reference',
    )

    # --- EMERGENCY CONTACT ---

    emergency_contact = fields.Char(
        string='Emergency Contact Name',
    )
    emergency_mobile = fields.Char(
        string='Emergency Mobile',
    )

    notes = fields.Text(string='Notes')

    # --- STATUS ---

    pass_state = fields.Selection(
        string='Status',
        required=True,
        default='active',
        tracking=True,
        selection=[
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled'),
        ],
    )

    _sql_constraints = [
        (
            'unique_pass_number',
            'UNIQUE(pass_number)',
            'Pass number must be unique.',
        ),
        (
            'unique_student_route_semester',
            'UNIQUE(student_id, route_id,'
            ' semester_id)',
            'Student already has a transport pass '
            'for this route and semester.',
        ),
    ]

    @api.onchange('route_id')
    def _onchange_route_id(self):
        """Auto-fill transport fee from route."""
        if self.route_id:
            stop_fee = (
                self.boarding_stop_id.stop_fee
                if self.boarding_stop_id
                and self.boarding_stop_id.stop_fee > 0
                else 0.0
            )
            self.transport_fee = (
                stop_fee
                if stop_fee > 0
                else self.route_id.fee_per_semester
            )
        else:
            self.transport_fee = 0.0

    @api.onchange('boarding_stop_id')
    def _onchange_boarding_stop(self):
        """Update fee when boarding stop changes."""
        if (self.boarding_stop_id
                and self.boarding_stop_id.stop_fee > 0):
            self.transport_fee = (
                self.boarding_stop_id.stop_fee
            )
        elif self.route_id:
            self.transport_fee = (
                self.route_id.fee_per_semester
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('pass_number'):
                vals['pass_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'oacis.transport.pass',
                    ) or '/'
                )
        return super().create(vals_list)

    def action_suspend(self):
        self.ensure_one()
        self.pass_state = 'suspended'
        self.message_post(
            body=_('Transport pass suspended.'),
        )

    def action_reactivate(self):
        self.ensure_one()
        if self.is_expired:
            raise UserError(
                _('Cannot reactivate an expired pass. '
                  'Please issue a new pass.'),
            )
        self.pass_state = 'active'
        self.message_post(
            body=_('Transport pass reactivated.'),
        )

    def action_cancel(self):
        self.ensure_one()
        self.pass_state = 'cancelled'
        self.message_post(
            body=_('Transport pass cancelled.'),
        )

    def action_mark_fee_paid(self):
        self.ensure_one()
        self.write({
            'fee_paid': True,
            'fee_paid_date': date.today(),
        })
        self.message_post(
            body=_('Transport fee of %s paid.')
                 % self.transport_fee,
        )
