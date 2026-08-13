import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OacisCampus(models.Model):
    """Extend oacis.campus with infrastructure management fields and workflow."""

    _inherit = 'oacis.campus'
    _check_company_auto = True

    building_ids = fields.One2many(
        comodel_name='oacis.building',
        inverse_name='campus_id',
        string='Buildings',
    )
    facility_ids = fields.One2many(
        comodel_name='oacis.facility',
        inverse_name='campus_id',
        string='Facilities',
    )
    building_count = fields.Integer(
        string='Total Buildings',
        compute='_compute_building_count',
        store=True,
    )
    facility_count = fields.Integer(
        string='Total Facilities',
        compute='_compute_facility_count',
        store=True,
    )
    room_count = fields.Integer(
        string='Total Rooms',
        compute='_compute_room_count',
        store=False,
    )
    total_room_capacity = fields.Integer(
        string='Total Room Capacity',
        compute='_compute_total_room_capacity',
        store=False,
    )
    campus_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Operational'),
            ('suspended', 'Suspended'),
            ('closed', 'Closed'),
        ],
        string='Campus State',
        default='draft',
        tracking=True,
    )

    @api.depends('building_ids')
    def _compute_building_count(self):
        for record in self:
            record.building_count = len(record.building_ids)

    @api.depends('facility_ids')
    def _compute_facility_count(self):
        for record in self:
            record.facility_count = len(record.facility_ids)

    def _compute_room_count(self):
        room_model = self.env['oacis.room']
        for record in self:
            record.room_count = room_model.search_count(
                [('campus_id', '=', record.id)],
            )

    def _compute_total_room_capacity(self):
        room_model = self.env['oacis.room']
        for record in self:
            rooms = room_model.search([('campus_id', '=', record.id)])
            record.total_room_capacity = sum(rooms.mapped('capacity'))

    def action_set_operational(self):
        for record in self:
            if not record.building_ids:
                raise UserError(
                    _('You must add at least one building before setting the campus to Operational.'),
                )
            record.campus_state = 'active'

    def action_suspend(self):
        self.campus_state = 'suspended'

    def action_close(self):
        self.campus_state = 'closed'

    def action_reset_draft(self):
        self.campus_state = 'draft'

    def action_open_buildings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Buildings'),
            'res_model': 'oacis.building',
            'view_mode': 'list,form,kanban',
            'domain': [('campus_id', '=', self.id)],
            'context': {'default_campus_id': self.id},
        }

    def action_open_rooms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rooms'),
            'res_model': 'oacis.room',
            'view_mode': 'list,form,kanban',
            'domain': [('campus_id', '=', self.id)],
            'context': {'default_campus_id': self.id},
        }

    def action_open_facilities(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facilities'),
            'res_model': 'oacis.facility',
            'view_mode': 'list,form',
            'domain': [('campus_id', '=', self.id)],
            'context': {'default_campus_id': self.id},
        }
