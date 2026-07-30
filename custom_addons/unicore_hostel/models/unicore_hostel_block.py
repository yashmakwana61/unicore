"""
UniCore Hostel Block Model
Represents a hostel building or residential wing.
Has a warden, gender restriction, and contains
multiple rooms.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreHostelBlock(models.Model):
    _name = 'unicore.hostel.block'
    _description = 'Hostel Block'
    _inherit = ['unicore.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(
        string='Block Name',
        required=True,
        tracking=True,
        help='e.g. Boys Hostel Block A, '
             'Girls Hostel Block 1',
    )
    code = fields.Char(
        string='Block Code',
        required=True,
        size=10,
        help='e.g. BH-A, GH-1',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )
    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        required=True,
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
    )

    # --- WARDEN ---

    warden_name = fields.Char(
        string='Warden Name',
        tracking=True,
    )
    warden_mobile = fields.Char(
        string='Warden Mobile',
    )
    warden_email = fields.Char(
        string='Warden Email',
    )
    asst_warden_name = fields.Char(
        string='Asst. Warden Name',
    )

    # --- BLOCK DETAILS ---

    gender_type = fields.Selection(
        string='For',
        required=True,
        default='male',
        tracking=True,
        selection=[
            ('male', 'Boys'),
            ('female', 'Girls'),
            ('mixed', 'Mixed / Co-ed'),
        ],
    )
    block_type = fields.Selection(
        string='Block Type',
        required=True,
        default='regular',
        selection=[
            ('regular', 'Regular'),
            ('ac', 'Air Conditioned'),
            ('premium', 'Premium / Suite'),
            ('faculty', 'Faculty Quarters'),
            ('guest', 'Guest House'),
        ],
    )
    total_floors = fields.Integer(
        string='Total Floors',
        default=1,
    )
    address = fields.Text(
        string='Block Address',
    )

    # --- FACILITIES ---

    has_wifi = fields.Boolean(
        string='Wi-Fi Available',
        default=True,
    )
    has_gym = fields.Boolean(
        string='Gym',
        default=False,
    )
    has_common_room = fields.Boolean(
        string='Common Room',
        default=True,
    )
    has_washing_machine = fields.Boolean(
        string='Washing Machine',
        default=False,
    )
    has_mess = fields.Boolean(
        string='Attached Mess',
        default=True,
    )
    mess_name = fields.Char(
        string='Mess Name',
        invisible_if='not has_mess',
    )
    monthly_mess_fee = fields.Monetary(
        string='Monthly Mess Fee',
        currency_field='currency_id',
        default=0.0,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
        store=True,
    )

    # --- ROOM STATS ---

    room_ids = fields.One2many(
        comodel_name='unicore.hostel.room',
        inverse_name='block_id',
        string='Rooms',
    )
    total_rooms = fields.Integer(
        string='Total Rooms',
        compute='_compute_room_stats',
        store=True,
    )
    total_capacity = fields.Integer(
        string='Total Capacity',
        compute='_compute_room_stats',
        store=True,
    )
    occupied_beds = fields.Integer(
        string='Occupied Beds',
        compute='_compute_room_stats',
        store=True,
    )
    available_beds = fields.Integer(
        string='Available Beds',
        compute='_compute_room_stats',
        store=True,
    )
    occupancy_rate = fields.Float(
        string='Occupancy Rate (%)',
        compute='_compute_room_stats',
        store=True,
        digits=(5, 1),
    )

    @api.depends(
        'room_ids',
        'room_ids.capacity',
        'room_ids.current_occupancy',
        'room_ids.room_state',
    )
    def _compute_room_stats(self):
        for rec in self:
            active_rooms = rec.room_ids.filtered(
                lambda r: r.room_state
                not in ('maintenance', 'closed')
            )
            rec.total_rooms = len(active_rooms)
            total_cap = sum(
                r.capacity for r in active_rooms
            )
            occupied = sum(
                r.current_occupancy
                for r in active_rooms
            )
            rec.total_capacity = total_cap
            rec.occupied_beds = occupied
            rec.available_beds = max(
                0, total_cap - occupied
            )
            rec.occupancy_rate = (
                round(
                    occupied / total_cap * 100, 1
                )
                if total_cap > 0 else 0.0
            )

    # --- STATUS ---

    block_state = fields.Selection(
        string='Status',
        required=True,
        default='active',
        tracking=True,
        selection=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('under_renovation', 'Under Renovation'),
            ('closed', 'Closed'),
        ],
    )
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        (
            'unique_block_code_company',
            'UNIQUE(code, company_id)',
            'Block code must be unique '
            'per institution.',
        ),
    ]

    def action_view_rooms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s Rooms') % self.name,
            'res_model': 'unicore.hostel.room',
            'view_mode': 'list,form',
            'domain': [('block_id', '=', self.id)],
            'context': {
                'default_block_id': self.id,
            },
        }
