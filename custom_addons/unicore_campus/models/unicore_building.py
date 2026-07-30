import logging

from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UnicoreBuilding(models.Model):
    """Represents a building within a campus."""

    _name = 'unicore.building'
    _description = 'Campus Building'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'campus_id, sequence, name'
    _check_company_auto = True

    name = fields.Char(
        string='Building Name',
        required=True,
        translate=True,
    )
    code = fields.Char(
        string='Building Code',
        required=True,
        size=10,
        help='Short code e.g. BLK-A, SCI-1',
    )
    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='campus_id.company_id',
        string='Institution',
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    floor_ids = fields.One2many(
        comodel_name='unicore.floor',
        inverse_name='building_id',
        string='Floors',
    )
    floor_count = fields.Integer(
        string='Number of Floors',
        compute='_compute_floor_count',
        store=True,
    )
    construction_year = fields.Integer(
        string='Construction Year',
    )
    total_area_sqft = fields.Float(
        string='Total Area (sq.ft)',
        digits=(10, 2),
    )
    building_type = fields.Selection(
        selection=[
            ('academic', 'Academic Block'),
            ('admin', 'Administration Block'),
            ('lab', 'Laboratory Block'),
            ('library', 'Library'),
            ('hostel', 'Hostel'),
            ('sports', 'Sports Facility'),
            ('cafeteria', 'Cafeteria'),
            ('other', 'Other'),
        ],
        string='Building Type',
        default='academic',
        required=True,
    )
    image = fields.Binary(
        string='Building Image',
        attachment=True,
    )

    _unique_building_code_campus = models.Constraint(
        'UNIQUE(code, campus_id)',
        'Building code must be unique per campus.',
    )

    @api.depends('floor_ids')
    def _compute_floor_count(self):
        for record in self:
            record.floor_count = len(record.floor_ids)

    @api.depends('name', 'code', 'campus_id')
    def _compute_display_name(self):
        for record in self:
            campus_code = record.campus_id.code if record.campus_id else ''
            record.display_name = f'[{record.code}] {record.name} ({campus_code})'

    @api.constrains('code')
    def _check_code_format(self):
        for record in self:
            if record.code:
                allowed = all(c.isalnum() or c in ('-', '_') for c in record.code)
                if not allowed:
                    raise ValidationError(
                        _('Building code must be uppercase alphanumeric with hyphens allowed.')
                    )
                if record.code != record.code.upper():
                    raise ValidationError(
                        _('Building code must be uppercase only.')
                    )

    @api.constrains('construction_year')
    def _check_construction_year(self):
        max_year = date.today().year + 5
        for record in self:
            if record.construction_year and (
                record.construction_year < 1800 or record.construction_year > max_year
            ):
                raise ValidationError(
                    _('Construction year must be between 1800 and %(max_year)s.', max_year=max_year)
                )

    def action_open_floors(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Floors'),
            'res_model': 'unicore.floor',
            'view_mode': 'list,form',
            'domain': [('building_id', '=', self.id)],
            'context': {'default_building_id': self.id},
        }
