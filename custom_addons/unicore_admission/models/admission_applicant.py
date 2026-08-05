from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AdmissionApplicant(models.Model):
    _name = 'unicore.admission.applicant'
    _description = 'Admission Applicant'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'application_number desc, id desc'
    _rec_name = 'name'
    _check_company_auto = True

    name = fields.Char(string='Full Name', required=True, tracking=True)
    middle_name = fields.Char(string='Middle Name')
    last_name = fields.Char(string='Last Name / Surname')
    email = fields.Char(string='Email', required=True, tracking=True)
    mobile = fields.Char(string='Mobile Number', required=True)
    phone = fields.Char(string='Phone')
    gender = fields.Selection(
        selection=[
            ('male', 'Male'), ('female', 'Female'),
            ('other', 'Other'), ('prefer_not', 'Prefer Not to Say'),
        ],
        string='Gender', required=True,
    )
    date_of_birth = fields.Date(string='Date of Birth', required=True, tracking=True)
    nationality_id = fields.Many2one(comodel_name='res.country', string='Nationality')
    image_1920 = fields.Binary(string='Photo', attachment=True)

    application_number = fields.Char(
        string='Application No.', readonly=True, copy=False,
        default=lambda self: _('New'), tracking=True,
    )
    cycle_id = fields.Many2one(
        comodel_name='unicore.admission.cycle', string='Admission Cycle',
        required=True, tracking=True,
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
        domain="[('program_id', '=', program_id)]",
    )
    # --- COHORT (Gap-3 fill) ---
    cohort_kind = fields.Selection(
        related='program_id.cohort_kind', string='Cohort Kind', readonly=True,
        help='How students of this program are grouped into cohorts '
             '(from the program).',
    )
    grade_level_id = fields.Many2one(
        comodel_name='unicore.academic.unit', string='Grade Level',
        domain="[('unit_type_id.code', '=', 'GRADE'), "
               "('company_id', '=', company_id)]",
        tracking=True, ondelete='restrict',
        help='Grade level for K-12 grade-batch programs (Gap-3 fill); '
             'propagated to the created student on admission confirmation.',
    )

    aggregate_percentage = fields.Float(
        string='Aggregate %', digits=(5, 2),
        help='Previous academic aggregate percentage',
    )
    entrance_score = fields.Float(
        string='Entrance Score', digits=(5, 2),
        help='Entrance test marks',
    )
    interview_score = fields.Float(
        string='Interview Score', digits=(5, 2),
    )
    composite_score = fields.Float(
        string='Composite Score', compute='_compute_composite_score',
        store=True,
    )

    documents_submitted = fields.Boolean(string='Documents Submitted', default=False, tracking=True)
    documents_verified = fields.Boolean(string='Documents Verified', default=False, tracking=True)

    guardian_name = fields.Char(string='Guardian Name')
    guardian_relation = fields.Char(string='Guardian Relation')
    guardian_mobile = fields.Char(string='Guardian Mobile')
    guardian_email = fields.Char(string='Guardian Email')

    state = fields.Selection(
        selection=[
            ('inquiry', 'Inquiry'),
            ('applied', 'Applied'),
            ('documents_pending', 'Documents Pending'),
            ('under_review', 'Under Review'),
            ('shortlisted', 'Shortlisted'),
            ('entrance_scheduled', 'Entrance Scheduled'),
            ('merit_listed', 'Merit Listed'),
            ('offer_sent', 'Offer Sent'),
            ('fee_pending', 'Fee Pending'),
            ('confirmed', 'Confirmed'),
            ('rejected', 'Rejected'),
            ('withdrawn', 'Withdrawn'),
            ('waitlisted', 'Waitlisted'),
        ],
        string='Status', default='inquiry', required=True, tracking=True,
    )
    rejection_reason = fields.Text(string='Rejection Reason')

    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='restrict', tracking=True,
    )
    offer_letter_ids = fields.One2many(
        comodel_name='unicore.admission.offer.letter',
        inverse_name='applicant_id', string='Offer Letters',
    )
    offer_letter_count = fields.Integer(
        string='Offer Count', compute='_compute_offer_letter_count', store=False,
    )
    student_id = fields.Many2one(
        comodel_name='unicore.student', string='Created Student',
        readonly=True, copy=False,
        help='Student record created when admission is confirmed.',
    )

    @api.depends('aggregate_percentage', 'entrance_score', 'interview_score')
    def _compute_composite_score(self):
        for record in self:
            record.composite_score = (
                (record.aggregate_percentage * 0.4) +
                (record.entrance_score * 0.4) +
                (record.interview_score * 0.2)
            )

    def _compute_offer_letter_count(self):
        for record in self:
            record.offer_letter_count = len(record.offer_letter_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('application_number', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('unicore.admission.applicant') or '/'
                vals['application_number'] = seq
        return super().create(vals_list)

    def action_apply(self):
        for record in self:
            if record.state != 'inquiry':
                raise UserError(_('Only inquiries can be converted to applications.'))
            record.write({'state': 'applied'})

    def action_submit_documents(self):
        for record in self:
            if record.state != 'applied':
                raise UserError(_('Documents can only be submitted after applying.'))
            record.write({'state': 'documents_pending', 'documents_submitted': True})

    def action_submit_for_review(self):
        for record in self:
            if record.state != 'documents_pending':
                raise UserError(_('Documents must be submitted before review.'))
            if not record.documents_submitted:
                raise UserError(_('Please confirm documents are submitted first.'))
            record.write({'state': 'under_review', 'documents_verified': True})

    def action_shortlist(self):
        for record in self:
            if record.state != 'under_review':
                raise UserError(_('Only applications under review can be shortlisted.'))
            record.write({'state': 'shortlisted'})

    def action_schedule_entrance(self):
        for record in self:
            if record.state != 'shortlisted':
                raise UserError(_('Only shortlisted applicants can be scheduled for entrance.'))
            record.write({'state': 'entrance_scheduled'})

    def action_add_to_merit(self):
        for record in self:
            if record.state not in ('entrance_scheduled', 'shortlisted'):
                raise UserError(_(
                    'Only shortlisted or entrance-scheduled applicants can be added to merit list.'
                ))
            record.write({'state': 'merit_listed'})

    def action_send_offer(self):
        OfferLetter = self.env['unicore.admission.offer.letter']
        for record in self:
            if record.state != 'merit_listed':
                raise UserError(_('Only merit-listed applicants can receive offers.'))
            offer = OfferLetter.create({
                'applicant_id': record.id,
                'offer_date': fields.Date.today(),
                'company_id': record.company_id.id,
            })
            record.write({'state': 'offer_sent'})

    def action_mark_fee_pending(self):
        for record in self:
            if record.state != 'offer_sent':
                raise UserError(_('Offer must be sent before fee is pending.'))
            record.write({'state': 'fee_pending'})

    def action_confirm_admission(self):
        Student = self.env['unicore.student']
        for record in self:
            if record.state != 'fee_pending':
                raise UserError(_('Fee must be confirmed before admission.'))
            batch_year = fields.Date.today().year
            if record.cycle_id.academic_year_id:
                code = record.cycle_id.academic_year_id.code
                batch_year = int(code[-4:]) if code and code[-4:].isdigit() else fields.Date.today().year

            student_vals = {
                'name': record.name,
                'middle_name': record.middle_name,
                'last_name': record.last_name,
                'email': record.email,
                'mobile': record.mobile,
                'gender': record.gender,
                'date_of_birth': record.date_of_birth,
                'nationality_id': record.nationality_id.id,
                'image_1920': record.image_1920,
                'campus_id': record.campus_id.id,
                'program_id': record.program_id.id,
                'specialisation_id': record.specialisation_id.id,
                'admission_date': fields.Date.today(),
                'batch_year': batch_year,
                'company_id': record.company_id.id,
                'admission_number': record.application_number,
            }
            if record.grade_level_id:
                student_vals['grade_level_id'] = record.grade_level_id.id
            student = Student.sudo().create(student_vals)
            record.write({'state': 'confirmed', 'student_id': student.id})

    def action_reject(self):
        for record in self:
            if record.state in ('confirmed', 'rejected', 'withdrawn'):
                raise UserError(_('Application already in a final state.'))
            if not record.rejection_reason:
                raise UserError(_('Please provide a rejection reason.'))
            record.write({'state': 'rejected'})

    def action_withdraw(self):
        for record in self:
            if record.state in ('confirmed', 'rejected', 'withdrawn'):
                raise UserError(_('Application already in a final state.'))
            record.write({'state': 'withdrawn'})

    def action_move_to_waitlist(self):
        for record in self:
            if record.state not in ('merit_listed', 'offer_sent', 'fee_pending'):
                raise UserError(_('Only active applications can be moved to waitlist.'))
            record.write({'state': 'waitlisted'})

    def action_open_offer_letters(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Offer Letters'),
            'res_model': 'unicore.admission.offer.letter',
            'view_mode': 'list,form',
            'domain': [('applicant_id', '=', self.id)],
            'context': {'default_applicant_id': self.id},
        }

    def action_open_student(self):
        self.ensure_one()
        if not self.student_id:
            raise UserError(_('No student record has been created for this applicant yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student'),
            'res_model': 'unicore.student',
            'view_mode': 'form',
            'res_id': self.student_id.id,
        }

    @api.constrains('date_of_birth')
    def _check_date_of_birth(self):
        for record in self:
            if record.date_of_birth and record.date_of_birth >= fields.Date.today():
                raise ValidationError(_('Date of birth must be in the past.'))

    @api.constrains('aggregate_percentage')
    def _check_aggregate(self):
        for record in self:
            if record.aggregate_percentage and (
                record.aggregate_percentage < 0 or record.aggregate_percentage > 100
            ):
                raise ValidationError(_('Aggregate percentage must be between 0 and 100.'))

    @api.constrains('entrance_score', 'interview_score')
    def _check_scores(self):
        for record in self:
            if record.entrance_score and record.entrance_score < 0:
                raise ValidationError(_('Entrance score cannot be negative.'))
            if record.interview_score and record.interview_score < 0:
                raise ValidationError(_('Interview score cannot be negative.'))

    @api.onchange('cycle_id')
    def _onchange_cycle_id(self):
        if self.cycle_id:
            self.campus_id = self.cycle_id.campus_id

    @api.onchange('program_id')
    def _onchange_program_id(self):
        if self.program_id:
            self.specialisation_id = False
            if self.program_id.cohort_kind != 'grade_batch':
                self.grade_level_id = False

    @api.constrains('program_id', 'grade_level_id')
    def _check_admission_cohort(self):
        """A grade-batch (K-12) program requires a grade level."""
        for record in self:
            if (record.program_id.cohort_kind == 'grade_batch'
                    and not record.grade_level_id):
                raise ValidationError(_(
                    'Grade level is required for grade-batch (K-12) '
                    'programs.'))

    @api.model
    def _read_group_state(self, states, domain, order):
        """Return all possible state values to display empty groups in kanban."""
        return [
            'inquiry', 'applied', 'documents_pending', 'under_review',
            'shortlisted', 'entrance_scheduled', 'merit_listed',
            'offer_sent', 'fee_pending', 'confirmed',
            'rejected', 'withdrawn', 'waitlisted'
        ]
