import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OacisRoom(models.Model):
    """Represents a room or hall within a building floor."""

    _name = 'oacis.room'
    _description = 'Room or Hall'
    _inherit = ['oacis.mixin', 'mail.thread']
    _order = 'campus_id, building_id, floor_id, name'
    _check_company_auto = True

    name = fields.Char(
        string='Room Name / Number',
        required=True,
    )
    code = fields.Char(
        string='Room Code',
        required=True,
        size=20,
        help='Unique room identifier e.g. A101, LAB-03',
    )
    floor_id = fields.Many2one(
        comodel_name='oacis.floor',
        string='Floor',
        required=True,
        ondelete='restrict',
    )
    building_id = fields.Many2one(
        comodel_name='oacis.building',
        related='floor_id.building_id',
        string='Building',
        store=True,
        readonly=True,
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus',
        related='floor_id.campus_id',
        string='Campus',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='floor_id.company_id',
        string='Institution',
        store=True,
        readonly=True,
    )
    room_type = fields.Selection(
        selection=[
            ('classroom', 'Classroom'),
            ('lecture_hall', 'Lecture Hall'),
            ('seminar', 'Seminar Room'),
            ('lab', 'Laboratory'),
            ('computer_lab', 'Computer Lab'),
            ('library', 'Library Hall'),
            ('exam_hall', 'Examination Hall'),
            ('conference', 'Conference Room'),
            ('staff_room', 'Staff Room'),
            ('office', 'Office'),
            ('other', 'Other'),
        ],
        string='Room Type',
        default='classroom',
        required=True,
    )
    capacity = fields.Integer(
        string='Seating Capacity',
        required=True,
        default=30,
    )
    exam_capacity = fields.Integer(
        string='Exam Capacity',
        default=0,
        help='Reduced capacity used during examinations',
    )
    has_projector = fields.Boolean(
        string='Has Projector',
        default=False,
    )
    has_ac = fields.Boolean(
        string='Has Air Conditioning',
        default=False,
    )
    has_smartboard = fields.Boolean(
        string='Has Smart Board',
        default=False,
    )
    has_internet = fields.Boolean(
        string='Has Internet Access',
        default=False,
    )
    room_state = fields.Selection(
        selection=[
            ('available', 'Available'),
            ('occupied', 'Occupied'),
            ('maintenance', 'Under Maintenance'),
            ('closed', 'Closed'),
        ],
        string='Room Status',
        default='available',
        tracking=True,
    )

    _unique_room_code_campus = models.Constraint(
        'UNIQUE(code, campus_id)',
        'Room code must be unique per campus.',
    )

    @api.constrains('capacity')
    def _check_capacity(self):
        for record in self:
            if record.capacity <= 0:
                raise ValidationError(
                    _('Seating capacity must be greater than zero.'),
                )

    @api.constrains('exam_capacity')
    def _check_exam_capacity(self):
        for record in self:
            if record.exam_capacity < 0:
                raise ValidationError(
                    _('Exam capacity must be a non-negative number.'),
                )
            if record.exam_capacity > record.capacity:
                raise ValidationError(
                    _('Exam capacity cannot exceed seating capacity.'),
                )
