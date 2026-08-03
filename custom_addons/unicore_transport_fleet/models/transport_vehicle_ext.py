from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TransportVehicleExt(models.Model):
    _inherit = 'unicore.transport.vehicle'

    fleet_vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Fleet Vehicle', readonly=True, copy=False,
        ondelete='set null', tracking=True,
        help='Odoo Fleet vehicle record mirroring this transport vehicle.')
    fleet_vehicle_count = fields.Integer(
        string='Fleet', compute='_compute_fleet_vehicle_count', store=False)

    @api.depends('fleet_vehicle_id')
    def _compute_fleet_vehicle_count(self):
        for rec in self:
            rec.fleet_vehicle_count = 1 if rec.fleet_vehicle_id else 0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.with_context(_fleet_sync=True)._sync_fleet_vehicle(create=True)
        return records

    def write(self, vals):
        res = super().write(vals)
        if ('registration_number' in vals or 'driver_name' in vals
                or 'vehicle_type' in vals or 'make' in vals
                or 'model_name' in vals or 'manufacture_year' in vals
                or 'color' in vals or 'seating_capacity' in vals
                or 'fuel_type' in vals or 'vehicle_state' in vals) \
                and not self.env.context.get('_fleet_sync'):
            for rec in self:
                rec._sync_fleet_vehicle(create=False)
        return res

    def _sync_fleet_vehicle(self, create=False):
        self.ensure_one()
        fleet = self.fleet_vehicle_id
        if not fleet:
            if not create:
                return
            fleet = self.env['fleet.vehicle'].sudo().with_context(
                _fleet_sync=True).create({
                    'name': self.registration_number or self.name,
                    'license_plate': self.registration_number,
                    'driver_id': self._get_driver_partner().id or False,
                    'model_id': self._get_fleet_model().id or False,
                    'seats': self.seating_capacity,
                    'color': self.color,
                    'fuel_type': self._get_fleet_fuel_type(),
                    'company_id': self.company_id.id,
                    'unicore_vehicle_id': self.id,
                })
            self.with_context(_fleet_sync=True).write(
                {'fleet_vehicle_id': fleet.id})
        else:
            vals = {}
            if 'registration_number' in self._context and \
                    not self.env.context.get('_fleet_sync'):
                vals['license_plate'] = self.registration_number
            if 'driver_name' in self._context and \
                    not self.env.context.get('_fleet_sync'):
                vals['driver_id'] = self._get_driver_partner().id or False
            if vals:
                fleet.sudo().with_context(
                    _fleet_sync=True).write(vals)

    def _get_driver_partner(self):
        self.ensure_one()
        if not self.driver_name:
            return self.env['res.partner']
        partner = self.env['res.partner'].search(
            [('name', '=', self.driver_name)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.driver_name,
                'phone': self.driver_mobile or False,
                'is_company': False,
            })
        return partner

    def _get_fleet_model(self):
        self.ensure_one()
        brand = self.env['fleet.vehicle.model.brand'].search(
            [('name', 'ilike', self.make)], limit=1)
        if not brand:
            brand = self.env['fleet.vehicle.model.brand'].create({
                'name': self.make or 'Unknown',
            })
        model = self.env['fleet.vehicle.model'].search(
            [('name', '=', self.model_name), ('brand_id', '=', brand.id)],
            limit=1)
        if not model:
            model = self.env['fleet.vehicle.model'].create({
                'name': self.model_name or self.vehicle_type or 'Other',
                'brand_id': brand.id,
            })
        return model

    def _get_fleet_fuel_type(self):
        mapping = {
            'diesel': 'diesel',
            'petrol': 'benzine',
            'cng': 'cng',
            'electric': 'electric',
            'hybrid': 'hybrid',
        }
        return mapping.get(self.fuel_type, 'diesel')

    def action_view_fleet_vehicle(self):
        self.ensure_one()
        if not self.fleet_vehicle_id:
            raise UserError(_(
                'No fleet vehicle linked to this transport vehicle yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fleet Vehicle'),
            'res_model': 'fleet.vehicle',
            'res_id': self.fleet_vehicle_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def action_sync_to_fleet(self):
        for rec in self:
            rec._sync_fleet_vehicle(create=True)
        return True