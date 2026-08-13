from odoo import fields, models


class OacisMixin(models.AbstractModel):
    _name = 'oacis.mixin'
    _description = 'Oacis Mixin'

    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this record will be hidden from most views.',
    )
    notes = fields.Text(
        string='Notes',
        help='Optional internal notes for this record.',
    )
    color = fields.Integer(
        string='Color Index',
        help='Color index for kanban view decoration.',
    )
