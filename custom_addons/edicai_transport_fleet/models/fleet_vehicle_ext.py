from odoo import fields, models


class FleetVehicleExt(models.Model):
    _inherit = 'fleet.vehicle'

    edicai_vehicle_id = fields.Many2one(
        'edicai.transport.vehicle', string='Edicai Vehicle',
        ondelete='set null', copy=False, readonly=True, tracking=True,
        help='Edicai transport vehicle this fleet record mirrors.')

    def write(self, vals):
        res = super().write(vals)
        if vals.get('license_plate') and self.edicai_vehicle_id:
            self.edicai_vehicle_id.with_context(
                _fleet_sync=True).write({
                    'registration_number': vals['license_plate']})
        if 'driver_id' in vals and self.edicai_vehicle_id:
            self.edicai_vehicle_id.with_context(
                _fleet_sync=True).write({
                    'driver_name': vals['driver_id'].name
                    if vals['driver_id'] else False})
        return res
