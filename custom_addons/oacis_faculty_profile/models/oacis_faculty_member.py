import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class FacultyMember(models.Model):
    _name = 'unicore.faculty.member'
    _description = 'Faculty Member (Academic Staff)'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'employee_id_number, name'
    _check_company_auto = True
    _rec_name = 'display_name'

    # === IDENTITY ===
    name = fields.Char(string='First Name', required=True, tracking=True)
    middle_name = fields.Char(string='Middle Name')
    last_name = fields.Char(string='Last Name', required=True, tracking=True)
    display_name = fields.Char(
        string='Full Name',
        compute='_compute_display_name',
        store=True,
    )
    employee_id_number = fields.Char(
        string='Employee ID',
        readonly=True,
        copy=False,
        help='Auto-generated unique faculty identifier',
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
    age = fields.Integer(
        string='Age',
        compute='_compute_age',
        store=False,
    )
    nationality_id = fields.Many2one('res.country', string='Nationality')
    national_id = fields.Char(string='National ID')
    passport_number = fields.Char(string='Passport Number')
    blood_group = fields.Selection([
        ('a+', 'A+'),
        ('a-', 'A-'),
        ('b+', 'B+'),
        ('b-', 'B-'),
        ('ab+', 'AB+'),
        ('ab-', 'AB-'),
        ('o+', 'O+'),
        ('o-', 'O-'),
        ('unknown', 'Unknown'),
    ], string='Blood Group', default='unknown')

    # === CONTACT ===
    email = fields.Char(string='Personal Email', required=True, tracking=True)
    institutional_email = fields.Char(string='Institutional Email', tracking=True)
    mobile = fields.Char(string='Mobile Number', required=True)
    phone = fields.Char(string='Office Phone')
    address_street = fields.Char(string='Street Address')
    address_city = fields.Char(string='City')
    address_state_id = fields.Many2one('res.country.state', string='State')
    address_zip = fields.Char(string='ZIP Code')
    address_country_id = fields.Many2one('res.country', string='Country')

    # === ACADEMIC DESIGNATION ===
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )
    campus_ids = fields.Many2many(
        'unicore.campus',
        'unicore_faculty_member_campus_rel',
        'faculty_member_id',
        'campus_id',
        string='Assigned Campuses',
        domain="[('company_id', '=', company_id)]",
    )
    primary_campus_id = fields.Many2one(
        'unicore.campus',
        string='Primary Campus',
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    academic_faculty_id = fields.Many2one(
        'unicore.faculty',
        string='Faculty / School',
        help='The academic faculty unit this member belongs to',
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    department_id = fields.Many2one(
        'unicore.department',
        string='Department',
        domain="[('faculty_id', '=', academic_faculty_id)]",
        tracking=True,
        required=True,
    )
    designation = fields.Selection([
        ('lecturer', 'Lecturer'),
        ('asst_professor', 'Assistant Professor'),
        ('assoc_professor', 'Associate Professor'),
        ('professor', 'Professor'),
        ('visiting', 'Visiting Faculty'),
        ('adjunct', 'Adjunct Faculty'),
        ('emeritus', 'Professor Emeritus'),
        ('instructor', 'Instructor'),
        ('teaching_assistant', 'Teaching Assistant'),
        ('research_associate', 'Research Associate'),
    ], string='Designation', default='lecturer', required=True, tracking=True)
    employment_type = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('visiting', 'Visiting'),
        ('contract', 'Contract'),
        ('adjunct', 'Adjunct'),
    ], string='Employment Type', default='full_time', required=True, tracking=True)
    specialisation_areas = fields.Text(
        string='Areas of Specialisation',
        help='Academic specialisation areas, comma separated',
    )
    joining_date = fields.Date(
        string='Joining Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    contract_end_date = fields.Date(
        string='Contract End Date',
        help='Leave empty for permanent staff',
        tracking=True,
    )
    years_of_experience = fields.Integer(
        string='Years of Experience',
        compute='_compute_years_of_experience',
        store=False,
    )
    is_hod = fields.Boolean(string='Is Head of Department', default=False, tracking=True)
    is_dean = fields.Boolean(string='Is Dean / Faculty Head', default=False, tracking=True)
    max_weekly_hours = fields.Integer(
        string='Max Weekly Teaching Hours',
        default=18,
        help='Maximum allowed teaching hours per week',
    )

    # === QUALIFICATIONS & PUBLICATIONS ===
    qualification_ids = fields.One2many(
        'unicore.faculty.qualification',
        'faculty_member_id',
        string='Academic Qualifications',
    )
    highest_qualification = fields.Char(
        string='Highest Qualification',
        compute='_compute_highest_qualification',
        store=False,
    )
    publication_ids = fields.One2many(
        'unicore.faculty.publication',
        'faculty_member_id',
        string='Publications & Research',
    )
    publication_count = fields.Integer(
        string='Publications',
        compute='_compute_publication_count',
        store=True,
    )

    # === WORKLOAD ===
    workload_ids = fields.One2many(
        'unicore.faculty.workload',
        'faculty_member_id',
        string='Workload Records',
    )
    current_weekly_hours = fields.Float(
        string='Current Weekly Hours',
        compute='_compute_current_weekly_hours',
        store=False,
        digits=(5, 1),
    )
    is_overloaded = fields.Boolean(
        string='Overloaded',
        compute='_compute_is_overloaded',
        store=True,
    )

    # === STATUS ===
    member_state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('sabbatical', 'On Sabbatical'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
        ('retired', 'Retired'),
    ], string='Employment Status', default='draft', required=True, tracking=True)
    termination_date = fields.Date(string='Termination / Retirement Date', tracking=True)
    termination_reason = fields.Text(string='Termination Reason')

    # === PORTAL ===
    partner_id = fields.Many2one('res.partner', string='Related Contact', copy=False)
    user_id = fields.Many2one('res.users', string='Related User Account', copy=False, tracking=True)

    _unique_faculty_employee_id = models.Constraint(
        'UNIQUE(employee_id_number)',
        'Employee ID must be globally unique.',
    )
    _unique_faculty_email_company = models.Constraint(
        'UNIQUE(email, company_id)',
        'Faculty member email must be unique per institution.',
    )

    # ---- Computed Fields ----

    @api.depends('name', 'middle_name', 'last_name')
    def _compute_display_name(self):
        for record in self:
            parts = [p for p in [record.name, record.middle_name, record.last_name] if p]
            record.display_name = ' '.join(parts) if parts else ''

    @api.depends('date_of_birth')
    def _compute_age(self):
        today = date.today()
        for record in self:
            if record.date_of_birth:
                delta = today - record.date_of_birth
                record.age = delta.days // 365
            else:
                record.age = 0

    @api.depends('joining_date')
    def _compute_years_of_experience(self):
        today = date.today()
        for record in self:
            if record.joining_date:
                delta = today - record.joining_date
                record.years_of_experience = delta.days // 365
            else:
                record.years_of_experience = 0

    @api.depends('qualification_ids', 'qualification_ids.is_highest')
    def _compute_highest_qualification(self):
        level_order = {
            'postdoc': 7,
            'phd': 6,
            'mphil': 5,
            'masters': 4,
            'professional': 3,
            'bachelors': 2,
            'diploma': 1,
            'other': 0,
        }
        for record in self:
            highest = record.qualification_ids.sorted(
                key=lambda q: level_order.get(q.qualification_level, 0),
                reverse=True,
            )
            record.highest_qualification = highest[:1].degree_title if highest else ''

    @api.depends('publication_ids')
    def _compute_publication_count(self):
        for record in self:
            record.publication_count = len(record.publication_ids)

    @api.depends('workload_ids', 'workload_ids.weekly_hours')
    def _compute_current_weekly_hours(self):
        for record in self:
            record.current_weekly_hours = sum(
                record.workload_ids.mapped('weekly_hours'),
            )

    @api.depends('current_weekly_hours', 'max_weekly_hours')
    def _compute_is_overloaded(self):
        for record in self:
            record.is_overloaded = (
                record.current_weekly_hours > record.max_weekly_hours
            )

    # ---- Constraints ----

    @api.constrains('date_of_birth')
    def _check_date_of_birth(self):
        for record in self:
            if record.date_of_birth and record.date_of_birth >= date.today():
                raise ValidationError(_('Date of birth must be in the past.'))
            if record.date_of_birth:
                delta = date.today() - record.date_of_birth
                if delta.days // 365 < 21:
                    raise ValidationError(_('Faculty member must be at least 21 years old.'))

    @api.constrains('joining_date', 'contract_end_date')
    def _check_dates(self):
        for record in self:
            if record.contract_end_date and record.joining_date and record.contract_end_date <= record.joining_date:
                raise ValidationError(_('Contract end date must be after joining date.'))

    @api.constrains('is_hod', 'department_id')
    def _check_is_hod(self):
        for record in self:
            if record.is_hod and not record.department_id:
                raise ValidationError(_('A department must be assigned when the member is marked as Head of Department.'))

    @api.constrains('is_dean', 'academic_faculty_id')
    def _check_is_dean(self):
        for record in self:
            if record.is_dean and not record.academic_faculty_id:
                raise ValidationError(_('A faculty/school must be assigned when the member is marked as Dean.'))

    @api.constrains('max_weekly_hours')
    def _check_max_weekly_hours(self):
        for record in self:
            if record.max_weekly_hours and (record.max_weekly_hours < 1 or record.max_weekly_hours > 40):
                raise ValidationError(_('Max weekly teaching hours must be between 1 and 40.'))

    # ---- Onchange ----

    @api.onchange('academic_faculty_id')
    def _onchange_academic_faculty_id(self):
        if self.academic_faculty_id:
            self.department_id = False

    # ---- Create / Write ----

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('employee_id_number'):
                vals['employee_id_number'] = self.env['ir.sequence'].next_by_code('unicore.faculty.member')
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
                _logger.warning("Could not auto-create partner for faculty member %s: %s", record.display_name, e)
        return records

    # ---- State Transitions ----

    def _post_status_message(self, old_state, new_state):
        self.message_post(
            body=_(
                'Faculty member status changed from <b>%(old)s</b> to <b>%(new)s</b>.',
                old=dict(self._fields['member_state'].selection).get(old_state, old_state),
                new=dict(self._fields['member_state'].selection).get(new_state, new_state),
            ),
            subtype_id=self.env.ref('mail.mt_note', raise_if_not_found=False).id,
        )

    def action_activate(self):
        self.ensure_one()
        if self.member_state != 'draft':
            raise UserError(_('Only draft faculty members can be activated.'))
        if not self.department_id:
            raise UserError(_('Department must be set before activating.'))
        if not self.email:
            raise UserError(_('Email must be set before activating.'))
        if not self.joining_date:
            raise UserError(_('Joining date must be set before activating.'))
        old = self.member_state
        self.write({'member_state': 'active'})
        self._post_status_message(old, 'active')

    def action_place_on_leave(self):
        self.ensure_one()
        if self.member_state != 'active':
            raise UserError(_('Only active faculty members can be placed on leave.'))
        old = self.member_state
        self.write({'member_state': 'on_leave'})
        self._post_status_message(old, 'on_leave')

    def action_sabbatical(self):
        self.ensure_one()
        if self.member_state != 'active':
            raise UserError(_('Only active faculty members can go on sabbatical.'))
        old = self.member_state
        self.write({'member_state': 'sabbatical'})
        self._post_status_message(old, 'sabbatical')

    def action_return_to_active(self):
        self.ensure_one()
        if self.member_state not in ('on_leave', 'sabbatical'):
            raise UserError(_('Only faculty members on leave or sabbatical can return to active.'))
        old = self.member_state
        self.write({'member_state': 'active'})
        self._post_status_message(old, 'active')

    def action_suspend(self):
        self.ensure_one()
        if self.member_state != 'active':
            raise UserError(_('Only active faculty members can be suspended.'))
        old = self.member_state
        self.write({'member_state': 'suspended'})
        self._post_status_message(old, 'suspended')

    def action_terminate(self):
        self.ensure_one()
        if self.member_state == 'terminated':
            raise UserError(_('Faculty member is already terminated.'))
        if not self.termination_reason:
            raise UserError(_('Termination reason is required.'))
        old = self.member_state
        self.write({
            'member_state': 'terminated',
            'termination_date': fields.Date.today(),
        })
        self._post_status_message(old, 'terminated')

    def action_retire(self):
        self.ensure_one()
        if self.member_state != 'active':
            raise UserError(_('Only active faculty members can be retired.'))
        old = self.member_state
        self.write({
            'member_state': 'retired',
            'termination_date': fields.Date.today(),
        })
        self._post_status_message(old, 'retired')

    def action_reset_draft(self):
        self.ensure_one()
        old = self.member_state
        self.write({'member_state': 'draft'})
        self._post_status_message(old, 'draft')

    # ---- Smart Button Actions ----

    def action_open_publications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Publications',
            'res_model': 'unicore.faculty.publication',
            'view_mode': 'list,form',
            'domain': [('faculty_member_id', '=', self.id)],
            'context': {
                'default_faculty_member_id': self.id,
            },
        }

    def action_open_workload(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Teaching Workload',
            'res_model': 'unicore.faculty.workload',
            'view_mode': 'list,form',
            'domain': [('faculty_member_id', '=', self.id)],
            'context': {
                'default_faculty_member_id': self.id,
            },
        }
