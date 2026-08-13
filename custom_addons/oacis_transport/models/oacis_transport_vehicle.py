"""
UniCore Transport Vehicle Model
University fleet vehicles with driver details,
capacity tracking and compliance document monitoring
(insurance, fitness certificate, permits).
"""

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UniCoreTransportVehicle(models.Model):
    _name = 'unicore.transport.vehicle'
    _description = 'Transport Vehicle'
    _inherit = ['unicore.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'registration_number'
    _check_company_auto = True

    name = fields.Char(
        string='Vehicle Name',
        required=True,
        help='e.g. Bus-01, Van-North',
    )
    registration_number = fields.Char(
        string='Registration Number',
        required=True,
        index=True,
        tracking=True,
        help='Official vehicle registration plate',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Home Campus',
        ondelete='set null',
        domain="[('company_id','=',company_id)]",
    )

    # --- VEHICLE DETAILS ---

    vehicle_type = fields.Selection(
        string='Vehicle Type',
        required=True,
        default='bus',
        selection=[
            ('bus', 'Bus'),
            ('minibus', 'Mini Bus'),
            ('van', 'Van'),
            ('car', 'Car'),
            ('tempo_traveller', 'Tempo Traveller'),
            ('other', 'Other'),
        ],
    )
    make = fields.Char(
        string='Make / Manufacturer',
        help='e.g. Tata, Ashok Leyland, Force',
    )
    model_name = fields.Char(
        string='Model',
        help='e.g. Starbus, Viking, Traveller',
    )
    manufacture_year = fields.Integer(
        string='Year of Manufacture',
    )
    color = fields.Char(
        string='Color',
    )
    seating_capacity = fields.Integer(
        string='Seating Capacity',
        required=True,
        default=40,
    )
    fuel_type = fields.Selection(
        string='Fuel Type',
        default='diesel',
        selection=[
            ('diesel', 'Diesel'),
            ('petrol', 'Petrol'),
            ('cng', 'CNG'),
            ('electric', 'Electric'),
            ('hybrid', 'Hybrid'),
        ],
    )

    # --- DRIVER ---

    driver_name = fields.Char(
        string='Driver Name',
        tracking=True,
    )
    driver_license = fields.Char(
        string='Driver License Number',
    )
    driver_mobile = fields.Char(
        string='Driver Mobile',
    )
    conductor_name = fields.Char(
        string='Conductor / Attendant',
    )
    conductor_mobile = fields.Char(
        string='Conductor Mobile',
    )

    # --- COMPLIANCE DOCUMENTS ---

    insurance_policy = fields.Char(
        string='Insurance Policy Number',
    )
    insurance_expiry = fields.Date(
        string='Insurance Expiry',
        tracking=True,
    )
    fitness_expiry = fields.Date(
        string='Fitness Certificate Expiry',
        tracking=True,
    )
    permit_expiry = fields.Date(
        string='Permit Expiry',
        tracking=True,
    )
    puc_expiry = fields.Date(
        string='PUC Certificate Expiry',
        tracking=True,
    )

    # --- COMPUTED COMPLIANCE STATUS ---

    days_to_insurance_expiry = fields.Integer(
        string='Insurance Expiry Days',
        compute='_compute_compliance_status',
        store=False,
    )
    days_to_fitness_expiry = fields.Integer(
        string='Fitness Expiry Days',
        compute='_compute_compliance_status',
        store=False,
    )
    is_insurance_expiring = fields.Boolean(
        string='Insurance Expiring Soon',
        compute='_compute_compliance_status',
        store=False,
    )
    is_fitness_expiring = fields.Boolean(
        string='Fitness Expiring Soon',
        compute='_compute_compliance_status',
        store=False,
    )

    @api.depends('insurance_expiry', 'fitness_expiry')
    def _compute_compliance_status(self):
        today = date.today()
        for rec in self:
            if rec.insurance_expiry:
                delta = (rec.insurance_expiry - today).days
                rec.days_to_insurance_expiry = delta
                rec.is_insurance_expiring = delta <= 30
            else:
                rec.days_to_insurance_expiry = 999
                rec.is_insurance_expiring = False

            if rec.fitness_expiry:
                delta = (rec.fitness_expiry - today).days
                rec.days_to_fitness_expiry = delta
                rec.is_fitness_expiring = delta <= 30
            else:
                rec.days_to_fitness_expiry = 999
                rec.is_fitness_expiring = False

    # --- ROUTE STATS ---

    route_ids = fields.One2many(
        comodel_name='unicore.transport.route',
        inverse_name='vehicle_id',
        string='Assigned Routes',
    )
    route_count = fields.Integer(
        string='Routes',
        compute='_compute_route_count',
        store=False,
    )
    current_pass_count = fields.Integer(
        string='Active Passes',
        compute='_compute_route_count',
        store=False,
    )

    def _compute_route_count(self):
        Pass = self.env['unicore.transport.pass']
        for rec in self:
            rec.route_count = len(rec.route_ids)
            rec.current_pass_count = Pass.search_count([
                ('vehicle_id', '=', rec.id),
                ('pass_state', '=', 'active'),
            ])

    # --- STATUS ---

    vehicle_state = fields.Selection(
        string='Status',
        required=True,
        default='active',
        tracking=True,
        selection=[
            ('active', 'Active'),
            ('maintenance', 'Under Maintenance'),
            ('retired', 'Retired'),
            ('breakdown', 'Breakdown'),
        ],
    )
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        (
            'unique_registration_number',
            'UNIQUE(registration_number)',
            'Vehicle registration number must '
            'be unique.',
        ),
    ]

    @api.constrains('seating_capacity')
    def _check_capacity(self):
        for rec in self:
            if rec.seating_capacity < 1:
                raise ValidationError(
                    _('Seating capacity must be '
                      'at least 1.'),
                )

    def action_view_routes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Routes'),
            'res_model': 'unicore.transport.route',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
        }

    def action_view_passes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Active Passes'),
            'res_model': 'unicore.transport.pass',
            'view_mode': 'list,form',
            'domain': [
                ('vehicle_id', '=', self.id),
                ('pass_state', '=', 'active'),
            ],
        }
