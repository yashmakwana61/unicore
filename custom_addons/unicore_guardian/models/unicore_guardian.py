"""
UniCore Guardian Model
Manages parent and guardian profiles as standalone
records that can be linked to multiple students.
"""
import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UniCoreGuardian(models.Model):
    _name = 'unicore.guardian'
    _description = 'Student Guardian / Parent'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'name, last_name'
    _check_company_auto = True
    _rec_name = 'display_name'

    # ------- IDENTITY FIELDS -------

    name = fields.Char(string='First Name', required=True, tracking=True)
    last_name = fields.Char(string='Last Name', required=True, tracking=True)
    display_name = fields.Char(
        string='Full Name',
        compute='_compute_display_name',
        store=True,
    )
    guardian_id_number = fields.Char(
        string='Guardian ID',
        readonly=True,
        copy=False,
        tracking=True,
        help='Auto-generated unique guardian identifier',
    )
    image_1920 = fields.Binary(string='Photo', attachment=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not', 'Prefer Not to Say'),
    ], string='Gender', required=True)
    date_of_birth = fields.Date(string='Date of Birth', tracking=True)
    age = fields.Integer(string='Age', compute='_compute_age', store=False)
    nationality_id = fields.Many2one('res.country', string='Nationality')
    national_id = fields.Char(string='National ID')
    passport_number = fields.Char(string='Passport Number')

    # ------- CONTACT FIELDS -------

    email = fields.Char(string='Email Address', required=True, tracking=True)
    mobile = fields.Char(string='Mobile Number', required=True, tracking=True)
    phone = fields.Char(string='Home / Office Phone')
    whatsapp_number = fields.Char(string='WhatsApp Number', help='If different from mobile')
    preferred_contact_method = fields.Selection([
        ('email', 'Email'),
        ('mobile', 'Mobile / SMS'),
        ('whatsapp', 'WhatsApp'),
        ('phone', 'Phone Call'),
    ], string='Preferred Contact Method', required=True, default='mobile')
    address_street = fields.Char(string='Street Address')
    address_street2 = fields.Char(string='Street Address 2')
    address_city = fields.Char(string='City')
    address_zip = fields.Char(string='ZIP / Postal Code')
    address_state_id = fields.Many2one('res.country.state', string='State / Province')
    address_country_id = fields.Many2one('res.country', string='Country')

    # ------- PROFESSIONAL FIELDS -------

    occupation = fields.Char(string='Occupation / Profession')
    employer_name = fields.Char(string='Employer / Business Name')
    employer_address = fields.Text(string='Employer Address')
    annual_income_range = fields.Selection([
        ('below_2l', 'Below ₹2 Lakhs'),
        ('2l_5l', '₹2 - 5 Lakhs'),
        ('5l_10l', '₹5 - 10 Lakhs'),
        ('10l_25l', '₹10 - 25 Lakhs'),
        ('25l_50l', '₹25 - 50 Lakhs'),
        ('above_50l', 'Above ₹50 Lakhs'),
        ('not_disclosed', 'Not Disclosed'),
    ], string='Annual Income Range', default='not_disclosed', help='Used for scholarship and financial aid assessment')

    # ------- INSTITUTION FIELDS -------

    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )

    # ------- STUDENT RELATIONSHIP FIELDS -------

    student_rel_ids = fields.One2many(
        'unicore.guardian.student.rel',
        'guardian_id',
        string='Ward Students',
    )
    student_count = fields.Integer(
        string='Number of Wards',
        compute='_compute_student_count',
        store=True,
    )

    # ------- FINANCIAL FIELDS -------

    is_primary_financial_guarantor = fields.Boolean(
        string='Primary Financial Guarantor',
        default=False,
        tracking=True,
        help='This guardian is financially responsible for fee payments',
    )
    guarantor_student_ids = fields.Many2many(
        'unicore.student',
        'unicore_guardian_guarantor_student_rel',
        'guardian_id',
        'student_id',
        string='Financial Responsibility For',
        help='Students for whom this guardian is the designated financial guarantor',
    )

    # ------- PORTAL ACCESS FIELDS -------

    partner_id = fields.Many2one(
        'res.partner',
        string='Related Contact',
        copy=False,
        help='Odoo partner for portal and communication',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Portal User Account',
        copy=False,
        tracking=True,
        help='Portal login account for this guardian',
    )
    has_portal_access = fields.Boolean(
        string='Has Portal Access',
        compute='_compute_has_portal_access',
        search='_search_has_portal_access',
        store=False,
    )
    portal_access_granted_on = fields.Datetime(
        string='Portal Access Granted On',
        readonly=True,
    )

    # ------- STATUS FIELDS -------

    guardian_state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deceased', 'Deceased'),
    ], string='Guardian Status', required=True, default='active', tracking=True)

    # ------- SQL CONSTRAINTS -------

    _sql_constraints = [
        (
            'unique_guardian_id_number',
            'UNIQUE(guardian_id_number)',
            'Guardian ID must be globally unique.',
        ),
        (
            'unique_guardian_email_company',
            'UNIQUE(email, company_id)',
            'A guardian with this email already exists in this institution.',
        ),
    ]

    # ------- CONSTRAINTS -------

    @api.constrains('date_of_birth')
    def _check_date_of_birth(self):
        for rec in self:
            if rec.date_of_birth:
                today = date.today()
                if rec.date_of_birth >= today:
                    raise ValidationError(
                        _('Date of birth must be in the past.'),
                    )
                age = today.year - rec.date_of_birth.year
                if (today.month, today.day) < (
                    rec.date_of_birth.month,
                    rec.date_of_birth.day,
                ):
                    age -= 1
                if age < 18:
                    raise ValidationError(
                        _('Guardian must be at least 18 years old.'),
                    )

    @api.constrains('email')
    def _check_email(self):
        for rec in self:
            if rec.email and '@' not in rec.email:
                raise ValidationError(
                    _('Please enter a valid email address.'),
                )

    # ------- COMPUTE METHODS -------

    @api.depends('name', 'last_name')
    def _compute_display_name(self):
        for rec in self:
            parts = [p for p in [rec.name, rec.last_name] if p]
            rec.display_name = ' '.join(parts)

    def _compute_age(self):
        for rec in self:
            if rec.date_of_birth:
                today = date.today()
                dob = rec.date_of_birth
                age = today.year - dob.year
                if (today.month, today.day) < (dob.month, dob.day):
                    age -= 1
                rec.age = age
            else:
                rec.age = 0

    @api.depends('student_rel_ids')
    def _compute_student_count(self):
        for rec in self:
            rec.student_count = len(rec.student_rel_ids)

    def _compute_has_portal_access(self):
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        for rec in self:
            if rec.user_id:
                rec.has_portal_access = (
                    portal_group in rec.user_id.groups_id
                )
            else:
                rec.has_portal_access = False

    def _search_has_portal_access(self, operator, value):
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('user_id.groups_id', 'in', portal_group.ids)]
        if (operator == '=' and not value) or (operator == '!=' and value):
            return ['|', ('user_id', '=', False), ('user_id.groups_id', 'not in', portal_group.ids)]
        raise NotImplementedError("Unsupported search operator for has_portal_access")

    # ------- CREATE OVERRIDE -------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('guardian_id_number'):
                vals['guardian_id_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'unicore.guardian',
                    ) or '/'
                )
        records = super().create(vals_list)
        for rec in records:
            if not rec.partner_id:
                try:
                    partner = self.env['res.partner'].create({
                        'name': rec.display_name,
                        'email': rec.email,
                        'phone': rec.phone or rec.mobile,
                        'image_1920': rec.image_1920,
                        'company_type': 'person',
                    })
                    rec.partner_id = partner.id
                except Exception as e:
                    _logger.warning("Could not auto-create partner for guardian %s: %s", rec.display_name, e)
        return records

    # ------- STATE METHODS -------

    def action_set_inactive(self):
        self.ensure_one()
        self.guardian_state = 'inactive'
        self.message_post(
            body=_('Guardian marked as Inactive.'),
        )

    def action_set_active(self):
        self.ensure_one()
        self.guardian_state = 'active'
        self.message_post(
            body=_('Guardian marked as Active.'),
        )

    def action_mark_deceased(self):
        self.ensure_one()
        self.guardian_state = 'deceased'
        self.message_post(
            body=_('Guardian record marked as Deceased.'),
        )

    # ------- PORTAL METHODS -------

    def action_grant_portal_access(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(
                _('A related contact must exist before '
                  'granting portal access. Please save '
                  'the record first.'),
            )
        if self.has_portal_access:
            raise UserError(
                _('This guardian already has portal access.'),
            )
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if self.user_id:
            self.user_id.write({
                'groups_id': [(4, portal_group.id)],
            })
        else:
            user = self.env['res.users'].with_context(
                no_reset_password=True,
            ).create({
                'name': self.display_name,
                'login': self.email,
                'email': self.email,
                'partner_id': self.partner_id.id,
                'groups_id': [(6, 0, [portal_group.id])],
            })
            self.user_id = user.id
        self.portal_access_granted_on = fields.Datetime.now()
        self.message_post(
            body=_(
                'Portal access granted by %s.',
            ) % self.env.user.name,
        )
        return {'type': 'ir.actions.client',
                'tag': 'reload'}

    def action_revoke_portal_access(self):
        self.ensure_one()
        if not self.has_portal_access:
            raise UserError(
                _('This guardian does not have portal access.'),
            )
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if self.user_id:
            self.user_id.write({
                'groups_id': [(3, portal_group.id)],
            })
        self.message_post(
            body=_(
                'Portal access revoked by %s.',
            ) % self.env.user.name,
        )

    def action_open_wards(self):
        """Open the list of students (wards) linked to this guardian."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Wards / Students'),
            'res_model': 'unicore.student',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.student_rel_ids.mapped('student_id').ids)],
            'context': {
                'default_company_id': self.company_id.id,
            },
        }
