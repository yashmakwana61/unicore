"""
UniCore Transport Trip Log Model
Daily trip records for tracking route operations,
attendance and incidents. One record per route
per trip per day.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class UniCoreTransportTrip(models.Model):
    _name = 'unicore.transport.trip'
    _description = 'Transport Trip Log'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'trip_date desc, route_id'
    _check_company_auto = True
    _rec_name = 'trip_number'

    trip_number = fields.Char(
        string='Trip Number',
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
    route_id = fields.Many2one(
        comodel_name='unicore.transport.route',
        string='Route',
        required=True,
        ondelete='restrict',
        index=True,
        domain="[('company_id','=',company_id)]",
    )
    vehicle_id = fields.Many2one(
        comodel_name='unicore.transport.vehicle',
        string='Vehicle',
        related='route_id.vehicle_id',
        store=True,
        readonly=True,
    )
    trip_date = fields.Date(
        string='Trip Date',
        required=True,
        default=fields.Date.today,
        index=True,
    )
    trip_type = fields.Selection(
        string='Trip Type',
        required=True,
        default='morning',
        selection=[
            ('morning', 'Morning (Pick-Up)'),
            ('evening', 'Evening (Drop)'),
            ('special', 'Special Trip'),
        ],
    )

    # --- TIMING ---

    scheduled_departure = fields.Float(
        string='Scheduled Departure',
        related='route_id.morning_departure_time',
        store=False,
        readonly=True,
    )
    actual_departure = fields.Float(
        string='Actual Departure Time',
        digits=(4, 2),
        help='Actual departure time (7.5 = 7:30)',
    )
    actual_arrival = fields.Float(
        string='Actual Arrival Time',
        digits=(4, 2),
    )
    delay_minutes = fields.Integer(
        string='Delay (Minutes)',
        compute='_compute_delay',
        store=True,
    )

    @api.depends('actual_departure',
                 'route_id.morning_departure_time',
                 'trip_type')
    def _compute_delay(self):
        for rec in self:
            if (rec.actual_departure > 0
                    and rec.route_id):
                scheduled = (
                    rec.route_id.morning_departure_time
                    if rec.trip_type == 'morning'
                    else rec.route_id
                    .evening_departure_time
                )
                delay_hours = (
                    rec.actual_departure - scheduled
                )
                rec.delay_minutes = max(
                    0,
                    int(delay_hours * 60)
                )
            else:
                rec.delay_minutes = 0

    # --- PASSENGER COUNT ---

    expected_passengers = fields.Integer(
        string='Expected Passengers',
        compute='_compute_expected_passengers',
        store=False,
    )
    actual_passengers = fields.Integer(
        string='Actual Passengers',
        default=0,
    )

    def _compute_expected_passengers(self):
        Pass = self.env['unicore.transport.pass']
        for rec in self:
            rec.expected_passengers = Pass.search_count([
                ('route_id', '=', rec.route_id.id),
                ('pass_state', '=', 'active'),
                ('valid_from', '<=', str(rec.trip_date)),
                ('valid_until', '>=', str(rec.trip_date)),
            ])

    # --- INCIDENT ---

    had_incident = fields.Boolean(
        string='Incident Reported',
        default=False,
        tracking=True,
    )
    incident_type = fields.Selection(
        string='Incident Type',
        selection=[
            ('breakdown', 'Vehicle Breakdown'),
            ('accident', 'Accident'),
            ('delay', 'Significant Delay'),
            ('passenger', 'Passenger Issue'),
            ('other', 'Other'),
        ],
    )
    incident_description = fields.Text(
        string='Incident Description',
    )

    # --- STATUS ---

    trip_state = fields.Selection(
        string='Status',
        required=True,
        default='scheduled',
        tracking=True,
        selection=[
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
    )
    cancellation_reason = fields.Char(
        string='Cancellation Reason',
    )
    driver_notes = fields.Text(
        string='Driver Notes',
    )

    _sql_constraints = [
        (
            'unique_trip_number',
            'UNIQUE(trip_number)',
            'Trip number must be unique.',
        ),
        (
            'unique_route_date_type',
            'UNIQUE(route_id, trip_date, trip_type)',
            'A trip log already exists for this '
            'route, date and trip type.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('trip_number'):
                vals['trip_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'unicore.transport.trip'
                    ) or '/'
                )
        return super().create(vals_list)

    def action_start(self):
        self.ensure_one()
        self.trip_state = 'in_progress'
        self.message_post(
            body=_('Trip started.')
        )

    def action_complete(self):
        self.ensure_one()
        self.trip_state = 'completed'
        self.message_post(
            body=_('Trip completed. Passengers: %d. '
                   'Delay: %d min.')
                 % (self.actual_passengers,
                    self.delay_minutes)
        )

    def action_cancel(self):
        self.ensure_one()
        self.trip_state = 'cancelled'
        self.message_post(
            body=_('Trip cancelled. Reason: %s')
                 % (self.cancellation_reason or '-')
        )
