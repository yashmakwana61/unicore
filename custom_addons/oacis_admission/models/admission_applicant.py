from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AdmissionApplicant(models.Model):
    _name = 'oacis.admission.applicant'
    _description = 'Admission Applicant'
    _inherit = ['oacis.mixin', 'oacis.sequence.mixin', 'mail.thread', 'mail.activity.mixin']
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
        comodel_name='oacis.admission.cycle', string='Admission Cycle',
        required=True, tracking=True,
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus', string='Campus', required=True,
        domain="[('company_id', '=', company_id)]", tracking=True,
    )
    program_id = fields.Many2one(
        comodel_name='oacis.program', string='Program', required=True,
        domain="[('company_id', '=', company_id)]", tracking=True,
    )
    specialisation_id = fields.Many2one(
        comodel_name='oacis.specialisation', string='Specialisation',
        domain="[('program_id', '=', program_id)]",
    )
    # --- COHORT (Gap-3 fill) ---
    cohort_kind = fields.Selection(
        related='program_id.cohort_kind', string='Cohort Kind', readonly=True,
        help='How students of this program are grouped into cohorts '
             '(from the program).',
    )
    grade_level_id = fields.Many2one(
        comodel_name='oacis.academic.unit', string='Grade Level',
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
    rank = fields.Integer(
        string='Merit Rank', compute='_compute_rank', store=False,
        help='Rank within the same cycle and program by composite score '
             '(1 = highest). Ties are broken by application number.',
    )
    # Cycle scoring weights surfaced for transparency on the applicant form.
    weight_aggregate = fields.Float(
        related='cycle_id.weight_aggregate', string='Aggregate Weight %',
        readonly=True,
    )
    weight_entrance = fields.Float(
        related='cycle_id.weight_entrance', string='Entrance Weight %',
        readonly=True,
    )
    weight_interview = fields.Float(
        related='cycle_id.weight_interview', string='Interview Weight %',
        readonly=True,
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
    stage_id = fields.Many2one(
        comodel_name='oacis.admission.stage',
        string='Stage',
        domain="[('company_id', '=', company_id)]",
        ondelete='restrict', tracking=True,
        help='Configurable pipeline stage. Kept in sync with the internal '
             'Status: changing the stage updates the status, and vice versa.',
    )
    color = fields.Integer(
        string='Color Index',
        help='Kanban card color, kept in sync with the current stage.',
    )
    rejection_reason = fields.Text(string='Rejection Reason')

    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='restrict', tracking=True,
    )
    offer_letter_ids = fields.One2many(
        comodel_name='oacis.admission.offer.letter',
        inverse_name='applicant_id', string='Offer Letters',
    )
    offer_letter_count = fields.Integer(
        string='Offer Count', compute='_compute_offer_letter_count', store=False,
    )
    student_id = fields.Many2one(
        comodel_name='oacis.student', string='Created Student',
        readonly=True, copy=False,
        help='Student record created when admission is confirmed.',
    )
    # --- PROGRAM ENROLLMENT (Phase 3) ---
    admission_enrollment_ids = fields.One2many(
        comodel_name='oacis.admission.enrollment',
        inverse_name='applicant_id', string='Program Enrollments',
    )
    admission_enrollment_count = fields.Integer(
        string='Program Enrollments',
        compute='_compute_admission_enrollment_count',
    )
    student_course_enrollment_ids = fields.One2many(
        comodel_name='oacis.enrollment',
        inverse_name='student_id',
        compute='_compute_student_course_enrollments',
        string='Course Enrollments',
        help='Course registrations of the student created on admission '
             'confirmation (read-only view).',
    )

    @api.depends('admission_enrollment_ids')
    def _compute_admission_enrollment_count(self):
        for record in self:
            record.admission_enrollment_count = len(
                record.admission_enrollment_ids)

    @api.depends('student_id.enrollment_ids')
    def _compute_student_course_enrollments(self):
        for record in self:
            record.student_course_enrollment_ids = (
                record.student_id.enrollment_ids
            )

    @api.depends(
        'aggregate_percentage', 'entrance_score', 'interview_score',
        'cycle_id.weight_aggregate', 'cycle_id.weight_entrance',
        'cycle_id.weight_interview',
    )
    def _compute_composite_score(self):
        """Weighted composite score using the cycle's configurable weights.

        Defaults to 40/40/20 (backward compatible) when the cycle does not
        define custom weights.
        """
        for record in self:
            w_agg = record.cycle_id.weight_aggregate or 40.0
            w_ent = record.cycle_id.weight_entrance or 40.0
            w_int = record.cycle_id.weight_interview or 20.0
            total = w_agg + w_ent + w_int or 100.0
            record.composite_score = (
                (record.aggregate_percentage * w_agg) +
                (record.entrance_score * w_ent) +
                (record.interview_score * w_int)
            ) / total

    @api.depends(
        'composite_score',
        'cycle_id.applicant_ids.composite_score',
    )
    def _compute_rank(self):
        """Merit rank within cycle + program by composite score.

        Non-stored: computed lazily for the records being displayed. Ties are
        broken by the application id (older application ranks higher).
        """
        for record in self:
            record.rank = 0
        if not self:
            return
        groups = {}
        for record in self:
            key = (record.cycle_id.id, record.program_id.id)
            groups.setdefault(key, self.env['oacis.admission.applicant'])
            groups[key] |= record
        for (cycle_id, program_id), applicants in groups.items():
            siblings = self.search([
                ('cycle_id', '=', cycle_id),
                ('program_id', '=', program_id),
            ])
            for record in applicants:
                better = siblings.filtered(
                    lambda a: (
                        a.composite_score > record.composite_score
                        or (
                            a.composite_score == record.composite_score
                            and a.id < record.id
                        )
                    ),
                )
                record.rank = len(better) + 1

    def _compute_offer_letter_count(self):
        for record in self:
            record.offer_letter_count = len(record.offer_letter_ids)

    @api.model_create_multi
    def create(self, vals_list):
        Stage = self.env['oacis.admission.stage']
        for vals in vals_list:
            company_id = vals.get('company_id') or self.env.company.id
            # Lazy seed: a company without a pipeline gets the 13 defaults.
            Stage._ensure_default_stages(self.env['res.company'].browse(company_id))
            if vals.get('application_number', _('New')) == _('New'):
                seq = self._next_sequence(
                    'oacis.admission.applicant', company_id=company_id,
                ) or '/'
                vals['application_number'] = seq
            if 'stage_id' not in vals:
                stage = Stage._get_stage_for_state(company_id, vals.get('state', 'inquiry'))
                if stage:
                    vals['stage_id'] = stage.id
        return super().create(vals_list)

    def write(self, vals):
        """Keep ``state`` and ``stage_id`` in sync.

        - Writing ``stage_id`` (kanban drag / Advance) drives ``state``.
        - Writing ``state`` (action buttons / API) drives ``stage_id``.
        The internal ``state`` always remains authoritative for business
        logic, CRM sync, reporting and the existing state-based buttons.
        """
        if 'stage_id' in vals and 'state' not in vals:
            res = super().write(vals)
            self._sync_state_from_stage()
            return res
        if 'state' in vals and 'stage_id' not in vals:
            res = super().write(vals)
            self._sync_stage_from_state()
            return res
        return super().write(vals)

    def _sync_state_from_stage(self):
        """Set ``state`` (and card color) to match the current ``stage_id``."""
        for record in self:
            if record.stage_id and record.stage_id.state != record.state:
                record.state = record.stage_id.state
            if record.stage_id and record.stage_id.color != record.color:
                record.color = record.stage_id.color

    def _sync_stage_from_state(self):
        """Set ``stage_id`` (and card color) to match the current ``state``."""
        for record in self:
            if not record.stage_id or record.stage_id.state != record.state:
                stage = self.env['oacis.admission.stage']._get_stage_for_state(
                    record.company_id.id, record.state)
                if stage:
                    record.stage_id = stage
                    if record.color != stage.color:
                        record.color = stage.color

    def action_advance_stage(self):
        """Move to the next stage by sequence (no-op from terminal stages)."""
        for record in self:
            if not record.stage_id:
                raise UserError(_('This applicant has no stage assigned.'))
            next_stage = record.stage_id._get_next_stage()
            if not next_stage:
                raise UserError(_(
                    'This applicant is already at the last stage ("%s").',
                ) % record.stage_id.name)
            record.stage_id = next_stage

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
                    'Only shortlisted or entrance-scheduled applicants can be added to merit list.',
                ))
            record.write({'state': 'merit_listed'})

    def action_send_offer(self):
        OfferLetter = self.env['oacis.admission.offer.letter']
        for record in self:
            if record.state != 'merit_listed':
                raise UserError(_('Only merit-listed applicants can receive offers.'))
            seat = self.env['oacis.admission.cycle.seat'].search([
                ('cycle_id', '=', record.cycle_id.id),
                ('program_id', '=', record.program_id.id),
            ], limit=1)
            if seat and seat.available_seats <= 0:
                raise UserError(_(
                    'No seats available for %s in cycle %s. '
                    'Reserve more seats or wait for an existing offer to be '
                    'declined.' % (seat.program_id.name, record.cycle_id.name),
                ))
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
        Student = self.env['oacis.student']
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
            'res_model': 'oacis.admission.offer.letter',
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
            'res_model': 'oacis.student',
            'view_mode': 'form',
            'res_id': self.student_id.id,
        }

    def action_enroll_in_program(self):
        """Open the 'Enroll in Program' wizard (Phase 3)."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_(
                'Only confirmed applicants can be enrolled in a program.'))
        if not self.student_id:
            raise UserError(_(
                'No student record has been created for this applicant yet. '
                'Confirm the admission first.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enroll in Program'),
            'res_model': 'oacis.admission.enrollment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_applicant_id': self.id},
        }

    def action_open_program_enrollment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Program Enrollments'),
            'res_model': 'oacis.admission.enrollment',
            'view_mode': 'list,form',
            'domain': [('applicant_id', '=', self.id)],
            'context': {'default_applicant_id': self.id},
        }

    def action_open_student_course_enrollments(self):
        self.ensure_one()
        if not self.student_id:
            raise UserError(_(
                'No student record has been created for this applicant yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Course Enrollments'),
            'res_model': 'oacis.enrollment',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.student_id.id)],
            'context': {'default_student_id': self.student_id.id},
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
