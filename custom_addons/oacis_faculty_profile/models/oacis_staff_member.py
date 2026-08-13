import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StaffMember(models.Model):
    _name = 'oacis.staff.member'
    _description = 'Administrative Staff Member'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'employee_id_number, name'
    _check_company_auto = True
    _rec_name = 'display_name'

    # === IDENTITY ===
    name = fields.Char(string='First Name', required=True, tracking=True)
    last_name = fields.Char(string='Last Name', required=True, tracking=True)
    display_name = fields.Char(
        string='Full Name',
        compute='_compute_display_name',
        store=True,
    )
    employee_id_number = fields.Char(
        string='Staff ID',
        readonly=True,
        copy=False,
        help='Auto-generated unique staff identifier',
        tracking=True,
    )
    image_1920 = fields.Binary(string='Photo', attachment=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not', 'Prefer Not to Say'),
    ], string='Gender', required=True)
    date_of_birth = fields.Date(string='Date of Birth')

    # === CONTACT ===
    email = fields.Char(string='Email', required=True, tracking=True)
    mobile = fields.Char(string='Mobile', required=True)
    phone = fields.Char(string='Office Phone')

    # === ORGANISATIONAL PLACEMENT ===
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )
    campus_id = fields.Many2one(
        'oacis.campus',
        string='Campus',
        required=True,
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    department_id = fields.Many2one('oacis.department', string='Department', tracking=True)
    staff_role = fields.Selection([
        ('registrar', 'Registrar'),
        ('admin_officer', 'Admin Officer'),
        ('finance_officer', 'Finance Officer'),
        ('library_staff', 'Library Staff'),
        ('it_support', 'IT Support'),
        ('hostel_warden', 'Hostel Warden'),
        ('transport_coordinator', 'Transport Coordinator'),
        ('receptionist', 'Receptionist'),
        ('counsellor', 'Student Counsellor'),
        ('security', 'Security Staff'),
        ('maintenance', 'Maintenance Staff'),
        ('other', 'Other'),
    ], string='Staff Role', default='admin_officer', required=True, tracking=True)
    employment_type = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('visiting', 'Visiting'),
        ('contract', 'Contract'),
        ('adjunct', 'Adjunct'),
    ], string='Employment Type', default='full_time', required=True, tracking=True)
    joining_date = fields.Date(
        string='Joining Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    contract_end_date = fields.Date(string='Contract End Date')
    oacis_group_id = fields.Many2one(
        'res.groups',
        string='Oacis Access Group',
        help='Oacis security group assigned to this staff member',
    )

    # === STATUS ===
    staff_state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
        ('retired', 'Retired'),
    ], string='Employment Status', default='draft', required=True, tracking=True)

    # === PORTAL ===
    partner_id = fields.Many2one('res.partner', string='Related Contact', copy=False)
    user_id = fields.Many2one('res.users', string='User Account', copy=False, tracking=True)

    _unique_staff_employee_id = models.Constraint(
        'UNIQUE(employee_id_number)',
        'Staff ID must be globally unique.',
    )
    _unique_staff_email_company = models.Constraint(
        'UNIQUE(email, company_id)',
        'Staff email must be unique per institution.',
    )

    # ---- Computed Fields ----

    @api.depends('name', 'last_name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.name} {record.last_name}".strip()

    # ---- Create / Write ----

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('employee_id_number'):
                vals['employee_id_number'] = self.env['ir.sequence'].next_by_code('oacis.staff.member')
        records = super().create(vals_list)
        for record in records:
            try:
                partner_vals = {
                    'name': record.display_name,
                    'email': record.email,
                    'phone': record.mobile,
                    'image_1920': record.image_1920,
                    'company_id': record.company_id.id,
                    'company_type': 'person',
                    'type': 'contact',
                }
                partner = self.env['res.partner'].sudo().create(partner_vals)
                record.partner_id = partner
            except Exception as e:
                _logger.warning("Could not auto-create partner for staff member %s: %s", record.display_name, e)
        return records

    # ---- State Transitions ----

    def _post_status_message(self, old_state, new_state):
        self.message_post(
            body=_(
                'Staff member status changed from <b>%(old)s</b> to <b>%(new)s</b>.',
                old=dict(self._fields['staff_state'].selection).get(old_state, old_state),
                new=dict(self._fields['staff_state'].selection).get(new_state, new_state),
            ),
            subtype_id=self.env.ref('mail.mt_note', raise_if_not_found=False).id,
        )

    def action_activate(self):
        self.ensure_one()
        if self.staff_state != 'draft':
            raise UserError(_('Only draft staff members can be activated.'))
        old = self.staff_state
        self.write({'staff_state': 'active'})
        self._post_status_message(old, 'active')

    def action_on_leave(self):
        self.ensure_one()
        if self.staff_state != 'active':
            raise UserError(_('Only active staff members can be placed on leave.'))
        old = self.staff_state
        self.write({'staff_state': 'on_leave'})
        self._post_status_message(old, 'on_leave')

    def action_return(self):
        self.ensure_one()
        if self.staff_state != 'on_leave':
            raise UserError(_('Only staff members on leave can return to active.'))
        old = self.staff_state
        self.write({'staff_state': 'active'})
        self._post_status_message(old, 'active')

    def action_suspend(self):
        self.ensure_one()
        if self.staff_state != 'active':
            raise UserError(_('Only active staff members can be suspended.'))
        old = self.staff_state
        self.write({'staff_state': 'suspended'})
        self._post_status_message(old, 'suspended')

    def action_terminate(self):
        self.ensure_one()
        if self.staff_state == 'terminated':
            raise UserError(_('Staff member is already terminated.'))
        old = self.staff_state
        self.write({'staff_state': 'terminated'})
        self._post_status_message(old, 'terminated')

    def action_retire(self):
        self.ensure_one()
        if self.staff_state != 'active':
            raise UserError(_('Only active staff members can be retired.'))
        old = self.staff_state
        self.write({'staff_state': 'retired'})
        self._post_status_message(old, 'retired')

    def action_reset_draft(self):
        self.ensure_one()
        old = self.staff_state
        self.write({'staff_state': 'draft'})
        self._post_status_message(old, 'draft')
