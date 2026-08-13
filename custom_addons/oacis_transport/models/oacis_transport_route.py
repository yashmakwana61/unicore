"""
Oacis Transport Route Model
A named transport route operated by the university
with ordered stops, distance and timing information.
A route has one primary vehicle assigned.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class OacisTransportRoute(models.Model):
    _name = 'oacis.transport.route'
    _description = 'Transport Route'
    _inherit = ['oacis.mixin', 'mail.thread']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(
        string='Route Name',
        required=True,
        tracking=True,
        help='e.g. Route 1 - Satellite to Campus',
    )
    code = fields.Char(
        string='Route Code',
        required=True,
        size=10,
        help='e.g. RT-01, RT-NORTH',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus',
        string='Campus',
        required=True,
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
    )
    vehicle_id = fields.Many2one(
        comodel_name='oacis.transport.vehicle',
        string='Assigned Vehicle',
        ondelete='set null',
        domain="[('vehicle_state','=','active'),"
               "('company_id','=',company_id)]",
        tracking=True,
    )
    direction = fields.Selection(
        string='Direction',
        required=True,
        default='both',
        selection=[
            ('pickup', 'Morning Pick-Up Only'),
            ('drop', 'Evening Drop Only'),
            ('both', 'Both (Pick-Up and Drop)'),
        ],
    )

    # --- TIMING ---

    morning_departure_time = fields.Float(
        string='Morning Departure Time',
        default=7.5,
        help='Departure from first stop (7.5 = 7:30)',
    )
    morning_arrival_time = fields.Float(
        string='Arrives at Campus',
        default=8.5,
        help='Arrival time at campus',
    )
    evening_departure_time = fields.Float(
        string='Evening Departure from Campus',
        default=17.0,
    )
    total_distance_km = fields.Float(
        string='Total Distance (km)',
        digits=(6, 2),
    )
    estimated_duration_minutes = fields.Integer(
        string='Estimated Duration (Minutes)',
        default=60,
    )

    # --- FEES ---

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
        store=True,
    )
    fee_per_semester = fields.Monetary(
        string='Fee Per Semester',
        currency_field='currency_id',
        default=0.0,
        help='Standard fee per student per semester',
    )

    # --- STOPS ---

    stop_ids = fields.One2many(
        comodel_name='oacis.transport.stop',
        inverse_name='route_id',
        string='Stops',
    )
    stop_count = fields.Integer(
        string='Stops',
        compute='_compute_stats',
        store=True,
    )
    active_pass_count = fields.Integer(
        string='Active Passes',
        compute='_compute_stats',
        store=True,
    )

    @api.depends('stop_ids',
                 'pass_ids',
                 'pass_ids.pass_state')
    def _compute_stats(self):
        for rec in self:
            rec.stop_count = len(rec.stop_ids)
            rec.active_pass_count = len(
                rec.pass_ids.filtered(
                    lambda p: p.pass_state == 'active',
                ),
            )

    pass_ids = fields.One2many(
        comodel_name='oacis.transport.pass',
        inverse_name='route_id',
        string='Passes',
    )

    # --- STATUS ---

    route_state = fields.Selection(
        string='Status',
        required=True,
        default='active',
        tracking=True,
        selection=[
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('discontinued', 'Discontinued'),
        ],
    )
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        (
            'unique_route_code_company',
            'UNIQUE(code, company_id)',
            'Route code must be unique per '
            'institution.',
        ),
    ]

    def action_view_passes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s Passes') % self.name,
            'res_model': 'oacis.transport.pass',
            'view_mode': 'list,form',
            'domain': [('route_id', '=', self.id)],
            'context': {
                'default_route_id': self.id,
            },
        }


class OacisTransportStop(models.Model):
    _name = 'oacis.transport.stop'
    _description = 'Transport Route Stop'
    _order = 'route_id, sequence'
    _check_company_auto = True

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    route_id = fields.Many2one(
        comodel_name='oacis.transport.route',
        string='Route',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(
        string='Stop Order',
        required=True,
        default=10,
        help='Order of this stop on the route '
             '(1 = first pick-up)',
    )
    name = fields.Char(
        string='Stop Name',
        required=True,
        help='e.g. Satellite Road Junction, '
             'Prahlad Nagar',
    )
    landmark = fields.Char(
        string='Landmark',
        help='Nearby landmark for easy identification',
    )
    area = fields.Char(
        string='Area / Locality',
    )
    pickup_time = fields.Float(
        string='Pick-Up Time',
        help='Scheduled pick-up time at this stop '
             '(7.5 = 7:30 AM)',
    )
    distance_from_campus_km = fields.Float(
        string='Distance from Campus (km)',
        digits=(5, 2),
    )
    stop_fee = fields.Monetary(
        string='Stop Fee (Semester)',
        currency_field='currency_id',
        default=0.0,
        help='Fee variant for students boarding '
             'at this stop (0 = use route fee)',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='route_id.currency_id',
        store=True,
        readonly=True,
    )
    is_active = fields.Boolean(
        string='Active Stop',
        default=True,
    )

    _sql_constraints = [
        (
            'unique_stop_sequence_route',
            'UNIQUE(route_id, sequence)',
            'Stop sequence must be unique per route.',
        ),
    ]
