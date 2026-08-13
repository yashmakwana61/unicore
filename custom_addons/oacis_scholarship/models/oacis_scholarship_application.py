"""
Oacis Scholarship Application Model
A student's application for a scholarship.
Auto-checks eligibility on submission.
Goes through review workflow before approval.
"""

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OacisScholarshipApplication(models.Model):
    _name = 'oacis.scholarship.application'
    _description = 'Scholarship Application'
    _inherit = ['oacis.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'application_date desc, student_id'
    _check_company_auto = True
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['application_number', 'student_id.display_name'],
    )

    @api.depends('application_number', 'student_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            student_name = (
                rec.student_id.display_name if rec.student_id else ''
            )
            if student_name:
                rec.display_name = '%s - %s' % (
                    rec.application_number, student_name,
                )
            else:
                rec.display_name = rec.application_number or ''

    application_number = fields.Char(
        string='Application Number',
        readonly=True,
        copy=False,
        index=True,
    )
    scholarship_program_id = fields.Many2one(
        comodel_name='oacis.scholarship.program',
        string='Scholarship Program',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('program_state','=','open'),"
               "('company_id','=',company_id)]",
    )
    student_id = fields.Many2one(
        comodel_name='oacis.student',
        string='Student',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('company_id','=',company_id),"
               "('student_state','in',"
               "['enrolled','active'])]",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Academic Year',
        related='scholarship_program_id.academic_year_id',
        store=True,
        readonly=True,
    )
    application_date = fields.Date(
        string='Application Date',
        required=True,
        default=fields.Date.today,
        readonly=True,
    )

    # --- STUDENT SNAPSHOT AT TIME OF APPLICATION ---

    student_cgpa = fields.Float(
        string='CGPA at Application',
        readonly=True,
        digits=(4, 2),
    )
    student_program_id = fields.Many2one(
        comodel_name='oacis.program',
        string='Program at Application',
        readonly=True,
    )
    student_year_of_study = fields.Integer(
        string='Year of Study',
        readonly=True,
    )
    student_attendance_percentage = fields.Float(
        string='Overall Attendance %',
        readonly=True,
        digits=(5, 2),
    )

    # --- SUPPORTING DOCUMENTS & INFO ---

    annual_family_income = fields.Monetary(
        string='Annual Family Income',
        currency_field='currency_id',
        help='Required for need-based scholarships',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='scholarship_program_id.currency_id',
        store=True,
        readonly=True,
    )
    statement_of_purpose = fields.Text(
        string='Statement of Purpose',
        help='Student statement explaining need/merit',
    )
    achievements = fields.Text(
        string='Achievements / Extracurriculars',
    )

    # --- ELIGIBILITY CHECK RESULTS ---

    eligibility_checked = fields.Boolean(
        string='Eligibility Checked',
        default=False,
        readonly=True,
    )
    is_eligible = fields.Boolean(
        string='Eligible',
        default=False,
        readonly=True,
        tracking=True,
    )
    eligibility_notes = fields.Text(
        string='Eligibility Check Notes',
        readonly=True,
    )

    # --- REVIEW ---

    reviewed_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Reviewed By',
        readonly=True,
    )
    review_date = fields.Date(
        string='Review Date',
        readonly=True,
    )
    review_notes = fields.Text(
        string='Review Notes / Remarks',
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
    )
    rank = fields.Integer(
        string='Merit Rank',
        default=0,
        help='Rank among all applicants for this program',
    )

    # --- AWARD LINK ---

    award_ids = fields.One2many(
        comodel_name='oacis.scholarship.award',
        inverse_name='application_id',
        string='Awards',
    )
    award_count = fields.Integer(
        string='Awards',
        compute='_compute_award_count',
        store=True,
    )

    @api.depends('award_ids')
    def _compute_award_count(self):
        for rec in self:
            rec.award_count = len(rec.award_ids)

    # --- STATUS ---

    application_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('under_review', 'Under Review'),
            ('shortlisted', 'Shortlisted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('withdrawn', 'Withdrawn by Student'),
        ],
    )

    _unique_student_scholarship_year = models.Constraint(
        'UNIQUE(student_id, scholarship_program_id)',
        'Student already applied for this scholarship program.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('application_number'):
                vals['application_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'oacis.scholarship.application',
                    ) or '/'
                )
        return super().create(vals_list)

    def _check_eligibility(self):
        """
        Auto-check student eligibility against program
        criteria. Returns (is_eligible, notes_list).
        """
        self.ensure_one()
        program = self.scholarship_program_id
        student = self.student_id
        notes = []
        is_eligible = True

        # CGPA check
        if program.min_cgpa > 0:
            if student.cgpa < program.min_cgpa:
                is_eligible = False
                notes.append(
                    _('CGPA %s is below required %s.')
                    % (round(student.cgpa, 2),
                       program.min_cgpa),
                )
            else:
                notes.append(
                    _('✓ CGPA %s meets minimum %s.')
                    % (round(student.cgpa, 2),
                       program.min_cgpa),
                )

        # Program eligibility check
        if program.eligible_program_ids:
            if (student.program_id
                    not in program.eligible_program_ids):
                is_eligible = False
                notes.append(
                    _('Program "%s" is not eligible '
                      'for this scholarship.')
                    % student.program_id.name,
                )
            else:
                notes.append(
                    _('✓ Program "%s" is eligible.')
                    % student.program_id.name,
                )

        # Year of study check
        min_yr = program.min_year_of_study
        max_yr = program.max_year_of_study
        yr = student.current_year_of_study
        if min_yr > 0 and yr < min_yr:
            is_eligible = False
            notes.append(
                _('Year of study %d is below '
                  'required minimum %d.')
                % (yr, min_yr),
            )
        if max_yr > 0 and yr > max_yr:
            is_eligible = False
            notes.append(
                _('Year of study %d exceeds '
                  'maximum %d.')
                % (yr, max_yr),
            )

        # Income check
        if program.max_annual_income > 0:
            if (self.annual_family_income
                    > program.max_annual_income):
                is_eligible = False
                notes.append(
                    _('Family income %s exceeds '
                      'maximum allowed %s.')
                    % (self.annual_family_income,
                       program.max_annual_income),
                )
            else:
                notes.append(
                    _('✓ Family income is within limit.'),
                )

        # Attendance check
        if program.min_attendance_percentage > 0:
            avg_att = self.student_attendance_percentage
            if avg_att < program.min_attendance_percentage:
                is_eligible = False
                notes.append(
                    _('Attendance %s%% is below '
                      'required %s%%.')
                    % (round(avg_att, 1),
                       program.min_attendance_percentage),
                )
            else:
                notes.append(
                    _('✓ Attendance %s%% meets minimum.')
                    % round(avg_att, 1),
                )

        # Deadline check
        if (program.application_deadline
                and date.today()
                > program.application_deadline):
            is_eligible = False
            notes.append(
                _('Application deadline %s has passed.')
                % program.application_deadline,
            )

        return is_eligible, '\n'.join(notes)

    def action_submit(self):
        self.ensure_one()
        student = self.student_id
        program = self.scholarship_program_id

        if program.program_state != 'open':
            raise UserError(
                _('This scholarship program is not '
                  'open for applications.'),
            )

        # Snapshot student data at submission
        att_records = self.env[
            'oacis.attendance.record'
        ].search([
            ('student_id', '=', student.id),
        ])
        avg_att = 0.0
        if att_records:
            total = len(att_records)
            present = len(att_records.filtered(
                lambda r: r.status in ('present', 'late'),
            ))
            avg_att = (
                present / total * 100 if total else 0.0
            )

        self.write({
            'student_cgpa': student.cgpa,
            'student_program_id': student.program_id.id,
            'student_year_of_study': (
                student.current_year_of_study
            ),
            'student_attendance_percentage': avg_att,
        })

        is_eligible, notes = self._check_eligibility()
        self.write({
            'eligibility_checked': True,
            'is_eligible': is_eligible,
            'eligibility_notes': notes,
            'application_state': 'submitted',
        })
        self.message_post(
            body=_('Application submitted. '
                   'Eligible: %s')
                 % (_('Yes') if is_eligible
                    else _('No')),
        )

    def action_start_review(self):
        self.ensure_one()
        self.write({
            'application_state': 'under_review',
            'reviewed_by_id': self.env.uid,
            'review_date': date.today(),
        })
        self.message_post(
            body=_('Application taken under review '
                   'by %s.') % self.env.user.name,
        )

    def action_shortlist(self):
        self.ensure_one()
        if not self.is_eligible:
            raise UserError(
                _('Cannot shortlist an ineligible '
                  'application. Use Override if '
                  'special circumstances apply.'),
            )
        self.application_state = 'shortlisted'
        self.message_post(
            body=_('Application shortlisted.'),
        )

    def action_approve(self):
        self.ensure_one()
        program = self.scholarship_program_id
        if program.approved_count >= program.total_quota:
            raise UserError(
                _('Scholarship quota of %d has been '
                  'reached. Cannot approve more '
                  'applications.')
                % program.total_quota,
            )
        self.application_state = 'approved'
        self.message_post(
            body=_('Scholarship application approved '
                   'by %s.') % self.env.user.name,
        )

    def action_reject(self):
        self.ensure_one()
        if not self.rejection_reason:
            raise UserError(
                _('Please provide a rejection reason '
                  'before rejecting.'),
            )
        self.application_state = 'rejected'
        self.message_post(
            body=_('Application rejected. Reason: %s')
                 % self.rejection_reason,
        )

    def action_withdraw(self):
        self.ensure_one()
        self.application_state = 'withdrawn'
        self.message_post(
            body=_('Application withdrawn by student.'),
        )
