import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class OacisFacility(models.Model):
    """Represents a facility available within a campus."""

    _name = 'oacis.facility'
    _description = 'Campus Facility'
    _inherit = ['oacis.mixin']
    _order = 'campus_id, name'
    _check_company_auto = True

    name = fields.Char(
        string='Facility Name',
        required=True,
        translate=True,
    )
    facility_type = fields.Selection(
        selection=[
            ('sports', 'Sports'),
            ('medical', 'Medical Center'),
            ('canteen', 'Canteen / Cafeteria'),
            ('bank', 'Bank / ATM'),
            ('transport', 'Transport'),
            ('parking', 'Parking'),
            ('gym', 'Gymnasium'),
            ('auditorium', 'Auditorium'),
            ('other', 'Other'),
        ],
        string='Facility Type',
        default='other',
        required=True,
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus',
        string='Campus',
        required=True,
        ondelete='restrict',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='campus_id.company_id',
        string='Institution',
        store=True,
        readonly=True,
    )
    capacity = fields.Integer(
        string='Capacity',
        default=0,
    )
    location_description = fields.Text(
        string='Location Description',
    )
    operating_hours = fields.Char(
        string='Operating Hours',
        help='e.g. Mon-Fri 8am-6pm',
    )
