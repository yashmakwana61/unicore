import logging

from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UnicoreStudent(models.Model):
    """Complete student record covering personal, academic and status information."""

    _name = 'unicore.student'
    _description = 'Student'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'student_id_number, name'
    _check_company_auto = True
    _rec_name = 'display_name'

    # --- IDENTITY ---
    name = fields.Char(string='Full Name', required=True, tracking=True)
    middle_name = fields.Char(string='Middle Name')
    last_name = fields.Char(string='Last Name / Surname')
    display_name = fields.Char(
        string='Display Name', compute='_compute_display_name', store=True
    )
    student_id_number = fields.Char(
        string='Student ID', readonly=True, copy=False,
        help='Auto-generated unique student identifier', tracking=True,
    )
    image_1920 = fields.Binary(string='Photo', attachment=True, help='Student passport photo')
    gender = fields.Selection(
        selection=[
            ('male', 'Male'), ('female', 'Female'),
            ('other', 'Other'), ('prefer_not', 'Prefer Not to Say'),
        ],
        string='Gender', required=True,
    )
    date_of_birth = fields.Date(string='Date of Birth', required=True, tracking=True)
    age = fields.Integer(string='Age', compute='_compute_age', store=False)
    place_of_birth = fields.Char(string='Place of Birth')
    nationality_id = fields.Many2one(comodel_name='res.country', string='Nationality')
    country_id = fields.Many2one(comodel_name='res.country', string='Country of Residence')
    state_id = fields.Many2one(
        comodel_name='res.country.state', string='State / Province',
        domain="[('country_id', '=', country_id)]",
    )
    religion = fields.Char(string='Religion', help='Optional — used for demographic reporting')
    blood_group = fields.Selection(
        selection=[
            ('a+', 'A+'), ('a-', 'A-'), ('b+', 'B+'), ('b-', 'B-'),
            ('ab+', 'AB+'), ('ab-', 'AB-'), ('o+', 'O+'), ('o-', 'O-'),
            ('unknown', 'Unknown'),
        ],
        string='Blood Group', default='unknown',
    )
    disability_status = fields.Selection(
        selection=[
            ('none', 'None'), ('visual', 'Visual Impairment'),
            ('hearing', 'Hearing Impairment'), ('physical', 'Physical Disability'),
            ('learning', 'Learning Disability'), ('other', 'Other'),
        ],
        string='Disability Status', default='none',
    )
    disability_details = fields.Text(
        string='Disability Details',
        help='Describe if disability_status is not none',
    )

    # --- IDENTIFICATION DOCUMENTS ---
    passport_number = fields.Char(string='Passport Number')
    passport_expiry = fields.Date(string='Passport Expiry Date')
    national_id = fields.Char(string='National ID / Aadhaar / NIC')
    visa_number = fields.Char(string='Visa Number', help='For international students')
    visa_expiry = fields.Date(string='Visa Expiry Date')
    is_international = fields.Boolean(string='International Student', default=False, tracking=True)

    # --- CONTACT ---
    email = fields.Char(string='Personal Email', required=True, tracking=True)
    institutional_email = fields.Char(
        string='Institutional Email', help='University-assigned email address', tracking=True,
    )
    mobile = fields.Char(string='Mobile Number', required=True)
    phone = fields.Char(string='Home Phone')
    address_street = fields.Char(string='Street Address')
    address_street2 = fields.Char(string='Street Address 2')
    address_city = fields.Char(string='City')
    address_zip = fields.Char(string='ZIP / Postal Code')
    address_state_id = fields.Many2one(comodel_name='res.country.state', string='State')
    address_country_id = fields.Many2one(comodel_name='res.country', string='Country')

    # --- ACADEMIC PLACEMENT ---
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='restrict', tracking=True,
    )
    campus_id = fields.Many2one(
        comodel_name='unicore.campus', string='Campus', required=True,
        domain="[('company_id', '=', company_id)]", tracking=True,
    )
    program_id = fields.Many2one(
        comodel_name='unicore.program', string='Program', required=True,
        domain="[('company_id', '=', company_id)]", tracking=True,
    )
    specialisation_id = fields.Many2one(
        comodel_name='unicore.specialisation', string='Specialisation',
        domain="[('program_id', '=', program_id)]", tracking=True,
    )
    department_id = fields.Many2one(
        comodel_name='unicore.department', related='program_id.department_id',
        store=True, readonly=True, string='Department',
    )
    faculty_id = fields.Many2one(
        comodel_name='unicore.faculty', related='program_id.faculty_id',
        store=True, readonly=True, string='Faculty',
    )
    batch_year = fields.Integer(
        string='Batch Year', required=True,
        default=lambda self: fields.Date.today().year,
        help='Year of admission e.g. 2024',
    )
    current_semester_id = fields.Many2one(
        comodel_name='unicore.semester', string='Current Semester', tracking=True,
    )
    current_academic_year_id = fields.Many2one(
        comodel_name='unicore.academic.year',
        related='current_semester_id.academic_year_id',
        store=True, readonly=True, string='Current Academic Year',
    )
    current_year_of_study = fields.Integer(string='Year of Study', default=1, help='Current year level')
    expected_graduation_date = fields.Date(string='Expected Graduation Date', tracking=True)
    actual_graduation_date = fields.Date(string='Actual Graduation Date', tracking=True)
    admission_date = fields.Date(
        string='Admission Date', required=True, default=fields.Date.today, tracking=True,
    )
    admission_number = fields.Char(string='Admission Number', help='Reference from admission process')

    # --- ACADEMIC PERFORMANCE ---
    cgpa = fields.Float(string='CGPA', default=0.0, digits=(4, 2), help='Cumulative Grade Point Average', tracking=True)
    total_credits_earned = fields.Integer(string='Credits Earned', default=0)
    total_credits_required = fields.Integer(
        string='Credits Required', related='program_id.total_credits', store=False,
    )
    completion_percentage = fields.Float(
        string='Completion %', compute='_compute_completion_percentage',
        store=False, digits=(5, 2),
    )

    # --- STUDENT STATUS ---
    student_state = fields.Selection(
        selection=[
            ('prospect', 'Prospect'), ('admitted', 'Admitted'),
            ('enrolled', 'Enrolled'), ('active', 'Active'),
            ('on_leave', 'On Leave'), ('graduated', 'Graduated'),
            ('alumni', 'Alumni'), ('withdrawn', 'Withdrawn'),
            ('expelled', 'Expelled'), ('deceased', 'Deceased'),
            ('cancelled', 'Cancelled'),
        ],
        string='Student Status', default='admitted', required=True, tracking=True,
    )
    status_change_reason = fields.Text(string='Status Change Reason', help='Reason for last status change')
    status_change_date = fields.Date(string='Status Changed On')

    # --- RELATIONS ---
    guardian_ids = fields.One2many(
        comodel_name='unicore.student.emergency.contact',
        inverse_name='student_id', string='Emergency Contacts / Guardians',
    )
    document_ids = fields.One2many(
        comodel_name='unicore.student.document',
        inverse_name='student_id', string='Documents',
    )
    document_count = fields.Integer(string='Document Count', compute='_compute_document_count', store=False)
    academic_history_count = fields.Integer(string='Academic History Count', compute='_compute_academic_history_count', store=False)
    academic_history_ids = fields.One2many(
        comodel_name='unicore.student.academic.history',
        inverse_name='student_id', string='Academic History',
    )

    # --- PORTAL ---
    partner_id = fields.Many2one(
        comodel_name='res.partner', string='Related Contact',
        help='Odoo partner record for portal access and invoicing',
        copy=False,
    )
    has_portal_access = fields.Boolean(string='Portal Access', compute='_compute_has_portal_access', store=False)

    # --- SYSTEM ---
    sequence = fields.Integer(string='Sequence', default=10)

    _unique_student_id_number = models.Constraint(
        'UNIQUE(student_id_number)',
        'Student ID must be globally unique.',
    )
    _unique_student_email_company = models.Constraint(
        'UNIQUE(email, company_id)',
        'A student with this email already exists.',
    )

    # -------------------- COMPUTE --------------------

    @api.depends('name', 'middle_name', 'last_name')
    def _compute_display_name(self):
        for record in self:
            parts = [p for p in (record.name, record.middle_name, record.last_name) if p]
            record.display_name = ' '.join(parts) if parts else record.name

    @api.depends('date_of_birth')
    def _compute_age(self):
        today = date.today()
        for record in self:
            if record.date_of_birth:
                age = today.year - record.date_of_birth.year
                if today.month < record.date_of_birth.month or (
                    today.month == record.date_of_birth.month and today.day < record.date_of_birth.day
                ):
                    age -= 1
                record.age = age
            else:
                record.age = 0

    @api.depends('total_credits_earned', 'program_id.total_credits')
    def _compute_completion_percentage(self):
        for record in self:
            if record.program_id and record.program_id.total_credits > 0:
                record.completion_percentage = (
                    record.total_credits_earned / record.program_id.total_credits * 100
                )
            else:
                record.completion_percentage = 0.0

    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    def _compute_academic_history_count(self):
        for record in self:
            record.academic_history_count = len(record.academic_history_ids)

    def _compute_has_portal_access(self):
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        for record in self:
            if record.partner_id and portal_group:
                record.has_portal_access = bool(
                    record.partner_id.user_ids.filtered(
                        lambda u: portal_group in u.group_ids
                    )
                )
            else:
                record.has_portal_access = False

    # -------------------- CONSTRAINTS --------------------

    @api.constrains('date_of_birth')
    def _check_date_of_birth(self):
        for record in self:
            if record.date_of_birth and record.date_of_birth >= date.today():
                raise ValidationError(_('Date of birth must be in the past.'))
            if record.age is not None and record.age < 14:
                raise ValidationError(_('Student must be at least 14 years old.'))

    @api.constrains('is_international', 'passport_number')
    def _check_international_passport(self):
        for record in self:
            if record.is_international and not record.passport_number:
                raise ValidationError(_('Passport number is required for international students.'))

    @api.constrains('disability_status', 'disability_details')
    def _check_disability_details(self):
        for record in self:
            if record.disability_status != 'none' and not record.disability_details:
                raise ValidationError(_('Please provide details about the disability.'))

    @api.constrains('expected_graduation_date', 'admission_date')
    def _check_graduation_date(self):
        for record in self:
            if record.expected_graduation_date and record.admission_date:
                if record.expected_graduation_date <= record.admission_date:
                    raise ValidationError(_('Expected graduation date must be after admission date.'))

    @api.constrains('student_state', 'actual_graduation_date')
    def _check_actual_graduation(self):
        for record in self:
            if record.student_state == 'graduated' and not record.actual_graduation_date:
                raise ValidationError(_('Actual graduation date is required when graduating a student.'))

    @api.constrains('visa_number', 'visa_expiry')
    def _check_visa_expiry(self):
        for record in self:
            if record.visa_number and record.visa_expiry and record.visa_expiry < date.today():
                raise ValidationError(_('Visa expiry date must be in the future.'))

    # -------------------- ONCHANGE --------------------

    @api.onchange('program_id')
    def _onchange_program_id(self):
        if self.program_id:
            if self.specialisation_id and self.specialisation_id.program_id != self.program_id:
                self.specialisation_id = False
            if self.admission_date and self.program_id.duration_years:
                dur_years = int(self.program_id.duration_years)
                self.expected_graduation_date = self.admission_date + timedelta(
                    days=dur_years * 365
                )

    # -------------------- CREATE OVERRIDE --------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('student_id_number'):
                seq = self.env['ir.sequence'].next_by_code('unicore.student') or '/'
                vals['student_id_number'] = seq

        records = super().create(vals_list)

        for record in records:
            if not record.partner_id:
                partner_vals = {
                    'name': record.display_name or record.name,
                    'email': record.email,
                    'phone': record.mobile,
                    'image_1920': record.image_1920,
                    'type': 'contact',
                    'company_id': record.company_id.id,
                    'company_type': 'person',
                }
                try:
                    partner = self.env['res.partner'].sudo().create(partner_vals)
                    record.partner_id = partner.id
                except Exception:
                    pass

        return records

    # -------------------- STATE TRANSITIONS --------------------

    def _post_status_message(self, old_state, new_state, reason=None):
        self.ensure_one()
        msg_parts = [
            _('Status changed from <strong>%(old)s</strong> to <strong>%(new)s</strong>.'),
        ]
        if reason:
            msg_parts.append(_('Reason: %s') % reason)
        msg_parts.append(_('Changed by: %s') % self.env.user.name)
        self.message_post(body='<br/>'.join(msg_parts))

    def action_enroll(self):
        self.ensure_one()
        if not self.campus_id:
            raise UserError(_('Campus must be set before enrollment.'))
        if not self.program_id:
            raise UserError(_('Program must be set before enrollment.'))
        if not self.batch_year:
            raise UserError(_('Batch year must be set before enrollment.'))
        old = self.student_state
        self.write({
            'student_state': 'enrolled',
            'status_change_date': date.today(),
        })
        self._post_status_message(old, 'enrolled')

    def action_activate(self):
        self.ensure_one()
        if not self.current_semester_id:
            raise UserError(_('Current semester must be set before activation.'))
        old = self.student_state
        self.write({
            'student_state': 'active',
            'status_change_date': date.today(),
        })
        self._post_status_message(old, 'active')

    def action_place_on_leave(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Place on Leave'),
            'res_model': 'unicore.student.status.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_student_id': self.id,
                'default_current_state': self.student_state,
                'default_target_state': 'on_leave',
            },
        }

    def action_return_from_leave(self):
        self.ensure_one()
        old = self.student_state
        self.write({
            'student_state': 'active',
            'status_change_date': date.today(),
            'status_change_reason': _('Returned from leave'),
        })
        self._post_status_message(old, 'active', _('Returned from leave'))

    def action_graduate(self):
        self.ensure_one()
        required = self.program_id.total_credits or 0
        if self.total_credits_earned < required:
            raise UserError(_(
                'Student has earned %(earned)d credits but %(required)d are required for graduation.',
                earned=self.total_credits_earned, required=required,
            ))
        old = self.student_state
        self.write({
            'student_state': 'graduated',
            'actual_graduation_date': date.today(),
            'status_change_date': date.today(),
        })
        self._post_status_message(old, 'graduated')

    def action_convert_to_alumni(self):
        self.ensure_one()
        old = self.student_state
        self.write({
            'student_state': 'alumni',
            'status_change_date': date.today(),
        })
        self._post_status_message(old, 'alumni')

    def action_withdraw(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Withdraw Student'),
            'res_model': 'unicore.student.status.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_student_id': self.id,
                'default_current_state': self.student_state,
                'default_target_state': 'withdrawn',
            },
        }

    def action_expel(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Expel Student'),
            'res_model': 'unicore.student.status.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_student_id': self.id,
                'default_current_state': self.student_state,
                'default_target_state': 'expelled',
            },
        }

    def action_mark_deceased(self):
        self.ensure_one()
        old = self.student_state
        self.write({
            'student_state': 'deceased',
            'status_change_date': date.today(),
        })
        self._post_status_message(old, 'deceased')

    def action_cancel(self):
        self.ensure_one()
        old = self.student_state
        self.write({
            'student_state': 'cancelled',
            'status_change_date': date.today(),
        })
        self._post_status_message(old, 'cancelled')

    def action_reactivate(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reactivate Student'),
            'res_model': 'unicore.student.status.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_student_id': self.id,
                'default_current_state': self.student_state,
                'default_target_state': 'admitted',
            },
        }

    # -------------------- SMART BUTTON ACTIONS --------------------

    def action_open_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'unicore.student.document',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_open_academic_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Academic History'),
            'res_model': 'unicore.student.academic.history',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
