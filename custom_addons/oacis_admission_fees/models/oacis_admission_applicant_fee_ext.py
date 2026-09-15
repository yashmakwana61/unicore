"""
Oacis Admission Applicant — Fees Bridge (Phase D)

Links the admission lifecycle to the fees module without touching either base
module (both ``oacis_admission`` and ``oacis_fees`` are loaded as dependencies,
which is exactly why this bridge module exists: neither can depend on the
other).

Behaviour added:

- Entering ``fee_pending`` (offer accepted) auto-creates the ``oacis.student``
  record and the admission ``oacis.fee.invoice`` for the cycle's academic year
  (first semester when one exists), using the applicable active fee structure.
  The invoice is linked to the applicant through ``applicant_id``.
- The invoice is idempotent: it is only generated once per applicant.
- ``action_confirm_admission`` keeps the existing "confirm the applicant and
  create the student" contract, but re-uses the student created at
  ``fee_pending`` instead of creating a duplicate, and refuses to confirm while
  a linked invoice is still unpaid.
"""

from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class OacisAdmissionApplicantFeeExt(models.Model):
    _inherit = 'oacis.admission.applicant'

    fee_invoice_ids = fields.One2many(
        comodel_name='oacis.fee.invoice',
        inverse_name='applicant_id', string='Fee Invoices',
    )
    fee_invoice_count = fields.Integer(
        string='Fee Invoices',
        compute='_compute_fee_invoice_count', store=True,
    )

    @api.depends('fee_invoice_ids')
    def _compute_fee_invoice_count(self):
        for record in self:
            record.fee_invoice_count = len(record.fee_invoice_ids)

    def action_open_fee_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fee Invoices'),
            'res_model': 'oacis.fee.invoice',
            'view_mode': 'list,form',
            'domain': [('applicant_id', '=', self.id)],
            'context': {'default_applicant_id': self.id},
        }

    # ------------------------------------------------------------------
    # Student creation at fee_pending (mirrors the base confirmation logic)
    # ------------------------------------------------------------------

    def _prepare_student_vals(self):
        """Same student values the base ``action_confirm_admission`` builds."""
        self.ensure_one()
        batch_year = fields.Date.today().year
        if self.cycle_id.academic_year_id:
            code = self.cycle_id.academic_year_id.code
            batch_year = (int(code[-4:]) if code and code[-4:].isdigit()
                          else fields.Date.today().year)
        vals = {
            'name': self.name,
            'middle_name': self.middle_name,
            'last_name': self.last_name,
            'email': self.email,
            'mobile': self.mobile,
            'gender': self.gender,
            'date_of_birth': self.date_of_birth,
            'nationality_id': self.nationality_id.id,
            'image_1920': self.image_1920,
            'campus_id': self.campus_id.id,
            'program_id': self.program_id.id,
            'specialisation_id': self.specialisation_id.id,
            'admission_date': fields.Date.today(),
            'batch_year': batch_year,
            'company_id': self.company_id.id,
            'admission_number': self.application_number,
        }
        if self.grade_level_id:
            vals['grade_level_id'] = self.grade_level_id.id
        return vals

    def _create_student(self):
        self.ensure_one()
        if not self.student_id:
            student = self.env['oacis.student'].sudo().create(
                self._prepare_student_vals(),
            )
            self.write({'student_id': student.id})
        return self.student_id

    # ------------------------------------------------------------------
    # Admission fee invoice generation
    # ------------------------------------------------------------------

    def _get_invoice_semester(self):
        self.ensure_one()
        return self.env['oacis.semester'].search([
            ('academic_year_id', '=', self.cycle_id.academic_year_id.id),
            ('company_id', '=', self.company_id.id),
        ], order='date_start, sequence, id', limit=1)

    def _get_invoice_structure(self, student, semester):
        self.ensure_one()
        FeeStructure = self.env['oacis.fee.structure']
        if semester:
            return FeeStructure.with_company(
                self.company_id).get_applicable_structure(student, semester)
        # No semester configured yet: fall back to the year's structures,
        # preferring an exact program/campus match.
        for domain_extra in [
            [('program_id', '=', student.program_id.id),
             ('campus_id', '=', student.campus_id.id)],
            [('program_id', '=', student.program_id.id),
             ('campus_id', '=', False)],
            [('program_id', '=', False), ('campus_id', '=', False)],
        ]:
            structure = FeeStructure.search([
                ('company_id', '=', self.company_id.id),
                ('academic_year_id', '=', self.cycle_id.academic_year_id.id),
                ('structure_state', '=', 'active'),
            ] + domain_extra, limit=1)
            if structure:
                return structure
        return FeeStructure.browse()

    def _generate_admission_fee_invoice(self):
        """Idempotently create the admission fee invoice for this applicant."""
        for record in self:
            if record.fee_invoice_ids:
                continue
            if not record.cycle_id.academic_year_id:
                continue
            student = record._create_student()
            semester = record._get_invoice_semester()
            structure = record._get_invoice_structure(student, semester)
            if not structure:
                record.message_post(body=_(
                    'No active fee structure applies to %s for %s. No fee '
                    'invoice was generated — confirm admission manually once '
                    'fees are settled.',
                ) % (record.name, record.cycle_id.academic_year_id.name))
                continue
            invoice_vals = {
                'student_id': student.id,
                'applicant_id': record.id,
                'company_id': record.company_id.id,
                'academic_year_id': record.cycle_id.academic_year_id.id,
                'semester_id': semester.id if semester else False,
                'invoice_date': date.today(),
                'due_date': date.today() + timedelta(days=30),
                'fee_structure_id': structure.id,
                'currency_id': structure.currency_id.id,
            }
            if structure.fee_due_date:
                invoice_vals['due_date'] = structure.fee_due_date
            invoice = self.env['oacis.fee.invoice'].with_company(
                record.company_id).create(invoice_vals)
            for sl in structure.line_ids:
                self.env['oacis.fee.invoice.line'].create({
                    'invoice_id': invoice.id,
                    'fee_type': sl.fee_type,
                    'name': sl.name,
                    'amount': sl.amount,
                    'is_mandatory': sl.is_mandatory,
                })
            record.message_post(body=_(
                'Fee invoice %s generated for %s.',
            ) % (invoice.invoice_number, structure.name))

    def action_generate_fee_invoice(self):
        """Manual regeneration entry point (idempotent) for the form button."""
        for record in self:
            if record.state != 'fee_pending':
                raise UserError(_(
                    'Fee invoices can only be generated once the offer is '
                    'accepted (fee pending).',
                ))
            record._generate_admission_fee_invoice()
        return True

    # ------------------------------------------------------------------
    # Lifecycle overrides
    # ------------------------------------------------------------------

    def action_mark_fee_pending(self):
        res = super().action_mark_fee_pending()
        for record in self:
            if record.state == 'fee_pending':
                record._generate_admission_fee_invoice()
        return res

    def action_confirm_admission(self):
        for record in self:
            if record.state != 'fee_pending':
                raise UserError(_('Fee must be confirmed before admission.'))
            open_invoices = record.fee_invoice_ids.filtered(
                lambda i: i.invoice_state not in ('paid', 'cancelled'),
            )
            if record.fee_invoice_ids and open_invoices:
                raise UserError(_(
                    'All fee invoices must be fully paid before confirming '
                    'admission.',
                ))
        already_have_student = self.filtered('student_id')
        no_student = self.filtered(lambda r: not r.student_id)
        if already_have_student:
            already_have_student.write({'state': 'confirmed'})
        if no_student:
            # Legacy path: the student was never pre-created (e.g. no fee
            # structure existed at fee_pending) — let the base create it.
            super(OacisAdmissionApplicantFeeExt, no_student).action_confirm_admission()
        return True