"""
UniCore Hostel Room Model
Individual room within a hostel block with
capacity, room type, amenities and current
occupancy tracking.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UniCoreHostelRoom(models.Model):
    _name = 'unicore.hostel.room'
    _description = 'Hostel Room'
    _rec_name = 'display_name'
    _inherit = ['unicore.mixin']

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['room_number', 'block_id.display_name'],
    )

    @api.depends('room_number', 'block_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            block_name = (
                rec.block_id.display_name if rec.block_id else ''
            )
            if block_name:
                rec.display_name = '%s - %s' % (
                    rec.room_number, block_name,
                )
            else:
                rec.display_name = rec.room_number or ''
    _order = 'block_id, floor_number, room_number'
    _check_company_auto = True

    room_number = fields.Char(
        string='Room Number',
        required=True,
        index=True,
    )
    block_id = fields.Many2one(
        comodel_name='unicore.hostel.block',
        string='Block',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        related='block_id.company_id',
        store=True,
        readonly=True,
    )
    floor_number = fields.Integer(
        string='Floor',
        default=1,
    )
    room_type = fields.Selection(
        string='Room Type',
        required=True,
        default='double',
        selection=[
            ('single', 'Single Occupancy'),
            ('double', 'Double Sharing'),
            ('triple', 'Triple Sharing'),
            ('quad', 'Four Sharing'),
            ('dormitory', 'Dormitory (6+)'),
        ],
    )
    capacity = fields.Integer(
        string='Capacity (Beds)',
        required=True,
        default=2,
    )
    current_occupancy = fields.Integer(
        string='Current Occupancy',
        compute='_compute_occupancy',
        store=True,
    )
    available_beds = fields.Integer(
        string='Available Beds',
        compute='_compute_occupancy',
        store=True,
    )
    is_full = fields.Boolean(
        string='Full',
        compute='_compute_occupancy',
        store=True,
    )

    @api.depends(
        'allocation_ids',
        'allocation_ids.allocation_state',
        'capacity',
    )
    def _compute_occupancy(self):
        for rec in self:
            active = rec.allocation_ids.filtered(
                lambda a: a.allocation_state
                == 'checked_in',
            )
            rec.current_occupancy = len(active)
            rec.available_beds = max(
                0, rec.capacity - len(active),
            )
            rec.is_full = (
                len(active) >= rec.capacity
            )

    allocation_ids = fields.One2many(
        comodel_name='unicore.hostel.allocation',
        inverse_name='room_id',
        string='Allocations',
    )

    # --- AMENITIES ---

    has_ac = fields.Boolean(
        string='Air Conditioning',
        default=False,
    )
    has_attached_bath = fields.Boolean(
        string='Attached Bathroom',
        default=False,
    )
    has_balcony = fields.Boolean(
        string='Balcony',
        default=False,
    )
    has_study_table = fields.Boolean(
        string='Study Table',
        default=True,
    )
    has_wardrobe = fields.Boolean(
        string='Wardrobe',
        default=True,
    )

    # --- FEES ---

    monthly_rent = fields.Monetary(
        string='Monthly Rent',
        currency_field='currency_id',
        default=0.0,
    )
    security_deposit = fields.Monetary(
        string='Security Deposit',
        currency_field='currency_id',
        default=0.0,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    # --- STATUS ---

    room_state = fields.Selection(
        string='Status',
        required=True,
        default='available',
        selection=[
            ('available', 'Available'),
            ('occupied', 'Fully Occupied'),
            ('partial', 'Partially Occupied'),
            ('maintenance', 'Under Maintenance'),
            ('reserved', 'Reserved'),
            ('closed', 'Closed'),
        ],
    )
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        (
            'unique_room_number_block',
            'UNIQUE(room_number, block_id)',
            'Room number must be unique per block.',
        ),
    ]

    @api.constrains('capacity')
    def _check_capacity(self):
        for rec in self:
            if rec.capacity < 1:
                raise ValidationError(
                    _('Room capacity must be at '
                      'least 1.'),
                )
