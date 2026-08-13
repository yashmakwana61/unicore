import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class UnicoreFloor(models.Model):
    """Represents a floor within a building."""

    _name = 'unicore.floor'
    _description = 'Building Floor'
    _inherit = ['unicore.mixin']
    _order = 'building_id, floor_number'
    _check_company_auto = True

    name = fields.Char(
        string='Floor Name',
        required=True,
        help='e.g. Ground Floor, First Floor, Basement',
    )
    floor_number = fields.Integer(
        string='Floor Number',
        required=True,
        help='Use 0 for Ground Floor, -1 for Basement',
    )
    building_id = fields.Many2one(
        comodel_name='unicore.building',
        string='Building',
        required=True,
        ondelete='restrict',
    )
    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        related='building_id.campus_id',
        string='Campus',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='building_id.company_id',
        string='Institution',
        store=True,
        readonly=True,
    )
    room_ids = fields.One2many(
        comodel_name='unicore.room',
        inverse_name='floor_id',
        string='Rooms',
    )
    room_count = fields.Integer(
        string='Rooms on Floor',
        compute='_compute_room_count',
        store=True,
    )

    _unique_floor_number_building = models.Constraint(
        'UNIQUE(floor_number, building_id)',
        'Floor number must be unique per building.',
    )

    @api.depends('room_ids')
    def _compute_room_count(self):
        for record in self:
            record.room_count = len(record.room_ids)

    def action_open_rooms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rooms'),
            'res_model': 'unicore.room',
            'view_mode': 'list,form,kanban',
            'domain': [('floor_id', '=', self.id)],
            'context': {'default_floor_id': self.id},
        }
