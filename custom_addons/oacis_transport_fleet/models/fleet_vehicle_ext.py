from odoo import fields, models


class FleetVehicleExt(models.Model):
    _inherit = 'fleet.vehicle'

    oacis_vehicle_id = fields.Many2one(
        'oacis.transport.vehicle', string='Oacis Vehicle',
        ondelete='set null', copy=False, readonly=True, tracking=True,
        help='Oacis transport vehicle this fleet record mirrors.')

    def write(self, vals):
        res = super().write(vals)
        if vals.get('license_plate') and self.oacis_vehicle_id:
            self.oacis_vehicle_id.with_context(
                _fleet_sync=True).write({
                    'registration_number': vals['license_plate']})
        if 'driver_id' in vals and self.oacis_vehicle_id:
            self.oacis_vehicle_id.with_context(
                _fleet_sync=True).write({
                    'driver_name': vals['driver_id'].name
                    if vals['driver_id'] else False})
        return res
