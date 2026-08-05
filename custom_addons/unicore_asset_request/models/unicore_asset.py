# -*- coding: utf-8 -*-
"""
UniCore Asset Model
Catalog of physical equipment and assets that can be requested
by faculty and staff — e.g. projectors, lab equipment, computers,
furniture, audio/video gear, vehicles.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreAsset(models.Model):
    _name = 'unicore.asset'
    _description = 'Asset'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'asset_type, name'
    _check_company_auto = True

    name = fields.Char(
        string='Asset Name',
        required=True,
        tracking=True,
    )

    code = fields.Char(
        string='Asset Code',
        required=True,
        copy=False,
        tracking=True,
        help='Unique asset identifier within the institution',
    )

    asset_type = fields.Selection(
        selection=[
            ('projector', 'Projector'),
            ('lab_equipment', 'Lab Equipment'),
            ('computer', 'Computer / Laptop'),
            ('furniture', 'Furniture'),
            ('audio_video', 'Audio / Video'),
            ('vehicle', 'Vehicle'),
            ('other', 'Other'),
        ],
        string='Asset Type',
        required=True,
        tracking=True,
    )

    description = fields.Text(
        string='Description',
        help='Detailed description of the asset',
    )

    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )

    building_id = fields.Many2one(
        comodel_name='unicore.building',
        string='Building',
        ondelete='restrict',
        tracking=True,
        domain="[('campus_id', '=', campus_id)]",
    )

    room_id = fields.Many2one(
        comodel_name='unicore.room',
        string='Room / Location',
        ondelete='restrict',
        tracking=True,
        domain="[('building_id', '=', building_id)]",
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    asset_state = fields.Selection(
        selection=[
            ('available', 'Available'),
            ('in_use', 'In Use'),
            ('maintenance', 'Under Maintenance'),
            ('retired', 'Retired'),
        ],
        string='Status',
        default='available',
        required=True,
        tracking=True,
    )

    image = fields.Binary(
        string='Image',
        attachment=True,
    )

    quantity_total = fields.Integer(
        string='Total Quantity',
        default=1,
        help='Total number of this asset available at the location',
    )

    quantity_available = fields.Integer(
        string='Available Quantity',
        compute='_compute_quantity_available',
        store=True,
    )

    current_request_ids = fields.One2many(
        comodel_name='unicore.asset.request',
        inverse_name='asset_id',
        string='Active Requests',
        domain="[('state', '=', 'approved')]",
    )

    request_count = fields.Integer(
        string='Request Count',
        compute='_compute_request_count',
    )

    @api.depends('quantity_total', 'current_request_ids', 'current_request_ids.requested_quantity')
    def _compute_quantity_available(self):
        for record in self:
            active_qty = sum(
                req.requested_quantity for req in record.current_request_ids
            )
            record.quantity_available = max(0, record.quantity_total - active_qty)

    def _compute_request_count(self):
        AssetRequest = self.env['unicore.asset.request']
        for record in self:
            record.request_count = AssetRequest.search_count([
                ('asset_id', '=', record.id),
            ])

    @api.constrains('code', 'company_id')
    def _check_code_unique(self):
        for record in self:
            if self.search_count([
                ('code', '=', record.code),
                ('company_id', '=', record.company_id.id),
                ('id', '!=', record.id),
            ]):
                raise ValidationError(_('Asset code must be unique within the institution.'))

    def action_view_requests(self):
        """Open the list of requests for this asset."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asset Requests'),
            'res_model': 'unicore.asset.request',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
        }
