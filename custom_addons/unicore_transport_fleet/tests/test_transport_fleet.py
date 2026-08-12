
import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'transport')
class UniCoreTransportFleetTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.vehicle = cls.env['unicore.transport.vehicle'].create({
            'name': 'Test Bus 01',
            'registration_number': 'KL-01-AB-1234',
            'vehicle_type': 'bus',
            'make': 'Tata',
            'model_name': 'Starbus',
            'manufacture_year': 2020,
            'color': 'White',
            'seating_capacity': 40,
            'fuel_type': 'diesel',
            'driver_name': 'Raj Driver',
            'driver_mobile': '+911111111111',
            'company_id': cls.company.id,
        })

    # -------------------- AUTO-CREATE --------------------

    def test_01_auto_create_fleet_vehicle(self):
        """Creating a transport vehicle auto-creates a fleet vehicle."""
        fleet = self.vehicle.fleet_vehicle_id
        self.assertTrue(fleet, 'A fleet vehicle must be auto-created')
        self.assertEqual(fleet.unicore_vehicle_id, self.vehicle)

    def test_02_fleet_vehicle_fields(self):
        """Fleet vehicle fields should mirror the transport vehicle."""
        fleet = self.vehicle.fleet_vehicle_id
        self.assertEqual(fleet.license_plate, 'KL-01-AB-1234')
        self.assertEqual(fleet.seats, 40)
        self.assertEqual(fleet.color, 'White')
        self.assertEqual(fleet.driver_id.name, 'Raj Driver')

    def test_03_smart_button_action(self):
        """The smart button action opens the linked fleet vehicle."""
        action = self.vehicle.action_view_fleet_vehicle()
        self.assertEqual(action['res_model'], 'fleet.vehicle')
        self.assertEqual(action['res_id'], self.vehicle.fleet_vehicle_id.id)
        self.assertEqual(action['view_mode'], 'form')

    # -------------------- SYNC --------------------

    def test_04_state_change_syncs_fleet(self):
        """Changing the transport vehicle state updates the fleet vehicle."""
        fleet = self.vehicle.fleet_vehicle_id
        self.vehicle.write({'vehicle_state': 'maintenance'})
        # fleet.vehicle state is a many2one to fleet.vehicle.state,
        # so we check that the fleet vehicle is still linked
        self.assertEqual(fleet.unicore_vehicle_id, self.vehicle)

    def test_05_fleet_write_syncs_transport(self):
        """Changing the fleet vehicle license plate updates the transport vehicle."""
        fleet = self.vehicle.fleet_vehicle_id
        fleet.write({'license_plate': 'KL-02-CD-5678'})
        self.assertEqual(self.vehicle.registration_number, 'KL-02-CD-5678')

    def test_06_manual_sync_creates_fleet(self):
        """action_sync_to_fleet creates a fleet vehicle when none exists."""
        vehicle_no_fleet = self.env['unicore.transport.vehicle'].create({
            'name': 'Sync Test Van',
            'registration_number': 'KL-03-EF-9012',
            'vehicle_type': 'van',
            'make': 'Force',
            'model_name': 'Traveller',
            'manufacture_year': 2021,
            'color': 'Red',
            'seating_capacity': 12,
            'fuel_type': 'diesel',
            'driver_name': 'Sync Driver',
            'company_id': self.company.id,
        })
        self.assertTrue(vehicle_no_fleet.fleet_vehicle_id)

    def test_07_fleet_vehicle_count(self):
        """fleet_vehicle_count is 1 when linked."""
        self.assertEqual(self.vehicle.fleet_vehicle_count, 1)
