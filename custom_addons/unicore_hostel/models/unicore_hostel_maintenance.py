"""
UniCore Hostel Maintenance Request Model
Students or wardens can log maintenance issues
for hostel rooms. Tracks priority, assignment
and resolution.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class UniCoreHostelMaintenance(models.Model):
    _name = 'unicore.hostel.maintenance'
    _description = 'Hostel Maintenance Request'
    _inherit = ['unicore.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'request_date desc, priority desc'
    _check_company_auto = True
    _rec_name = 'request_number'

    request_number = fields.Char(
        string='Request Number',
        readonly=True,
        copy=False,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    room_id = fields.Many2one(
        comodel_name='unicore.hostel.room',
        string='Room',
        required=True,
        ondelete='restrict',
        index=True,
        domain="[('company_id','=',company_id)]",
    )
    block_id = fields.Many2one(
        comodel_name='unicore.hostel.block',
        string='Block',
        related='room_id.block_id',
        store=True,
        readonly=True,
    )
    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Reported By (Student)',
        ondelete='set null',
        domain="[('company_id','=',company_id)]",
    )
    request_date = fields.Date(
        string='Request Date',
        required=True,
        default=fields.Date.today,
        readonly=True,
    )
    issue_type = fields.Selection(
        string='Issue Type',
        required=True,
        default='electrical',
        selection=[
            ('electrical', 'Electrical'),
            ('plumbing', 'Plumbing'),
            ('furniture', 'Furniture'),
            ('cleaning', 'Cleaning'),
            ('pest_control', 'Pest Control'),
            ('internet', 'Internet / Wi-Fi'),
            ('ac', 'Air Conditioning'),
            ('door_window', 'Door / Window'),
            ('other', 'Other'),
        ],
    )
    priority = fields.Selection(
        string='Priority',
        required=True,
        default='normal',
        selection=[
            ('low', 'Low'),
            ('normal', 'Normal'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ],
        tracking=True,
    )
    description = fields.Text(
        string='Issue Description',
        required=True,
    )
    assigned_to = fields.Char(
        string='Assigned To',
        tracking=True,
        help='Name of maintenance staff assigned',
    )
    resolution_notes = fields.Text(
        string='Resolution Notes',
    )
    resolved_date = fields.Date(
        string='Resolved On',
        readonly=True,
    )
    resolution_days = fields.Integer(
        string='Days to Resolve',
        compute='_compute_resolution_days',
        store=False,
    )

    @api.depends('request_date', 'resolved_date')
    def _compute_resolution_days(self):
        today = date.today()
        for rec in self:
            if rec.resolved_date and rec.request_date:
                delta = (
                    rec.resolved_date
                    - rec.request_date
                )
                rec.resolution_days = delta.days
            elif rec.request_date:
                delta = today - rec.request_date
                rec.resolution_days = delta.days
            else:
                rec.resolution_days = 0

    maintenance_state = fields.Selection(
        string='Status',
        required=True,
        default='open',
        tracking=True,
        selection=[
            ('open', 'Open'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
            ('cancelled', 'Cancelled'),
        ],
    )

    _sql_constraints = [
        (
            'unique_request_number',
            'UNIQUE(request_number)',
            'Request number must be unique.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('request_number'):
                vals['request_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'unicore.hostel.maintenance'
                    ) or '/'
                )
        return super().create(vals_list)

    def action_start(self):
        self.ensure_one()
        self.maintenance_state = 'in_progress'
        self.message_post(
            body=_('Maintenance started by %s.')
                 % self.env.user.name
        )

    def action_resolve(self):
        self.ensure_one()
        if not self.resolution_notes:
            raise UserError(
                _('Please add resolution notes '
                  'before marking as resolved.')
            )
        self.write({
            'maintenance_state': 'resolved',
            'resolved_date': date.today(),
        })
        self.message_post(
            body=_('Issue resolved. %s')
                 % self.resolution_notes
        )

    def action_cancel(self):
        self.ensure_one()
        self.maintenance_state = 'cancelled'
        self.message_post(
            body=_('Request cancelled.')
        )

    def action_reopen(self):
        self.ensure_one()
        self.maintenance_state = 'open'
        self.resolved_date = False
        self.message_post(
            body=_('Issue reopened.')
        )
