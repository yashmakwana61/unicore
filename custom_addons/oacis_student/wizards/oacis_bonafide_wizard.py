from odoo import fields, models


class UniCoreBonafideWizard(models.TransientModel):
    _name = 'unicore.bonafide.wizard'
    _description = 'Bonafide Certificate Wizard'

    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get('active_id'),
    )
    purpose = fields.Selection(
        selection=[
            ('bank_loan', 'Bank Loan / Education Loan'),
            ('passport', 'Passport Application'),
            ('visa', 'Visa Application'),
            ('scholarship', 'Scholarship Application'),
            ('employment', 'Employment Verification'),
            ('higher_studies', 'Higher Studies Abroad'),
            ('other', 'Other'),
        ],
        string='Purpose',
        required=True,
        default='bank_loan',
    )
    purpose_other = fields.Char(string='Specify Purpose')
    certificate_number = fields.Char(
        string='Certificate Number',
        readonly=True,
    )

    def _get_purpose_label(self):
        self.ensure_one()
        labels = {
            'bank_loan': 'obtaining an Education Loan',
            'passport': 'Passport Application',
            'visa': 'Visa Application',
            'scholarship': 'applying for a Scholarship',
            'employment': 'Employment Verification',
            'higher_studies': 'pursuing Higher Studies Abroad',
        }
        if self.purpose == 'other':
            return self.purpose_other or 'general purposes'
        return labels.get(self.purpose, self.purpose)

    def action_print(self):
        self.ensure_one()
        if not self.certificate_number:
            self.certificate_number = (
                self.env['ir.sequence'].next_by_code('unicore.bonafide.certificate') or '/'
            )

        student = self.student_id
        duration = student.program_id.duration_years if student.program_id else 4
        graduation_year = (student.batch_year or 0) + int(duration)

        data = {
            'purpose': self.purpose,
            'purpose_label': self._get_purpose_label(),
            'purpose_other': self.purpose_other,
            'certificate_number': self.certificate_number,
            'graduation_year': graduation_year,
        }
        return self.env.ref('unicore_student.action_report_bonafide').report_action(
            self.student_id, data=data,
        )
