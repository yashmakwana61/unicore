"""
Oacis Admission Entrance Test — Precision Fixes (Phase B)
Additive extension of ``oacis.admission.entrance.test`` and its line model:

- ``action_publish_results`` full override: the base implementation guards with
  ``line.attended and line.marks_obtained < 0`` which can NEVER fire because
  ``marks_obtained`` defaults to 0.0. This override tracks whether marks were
  actually entered via a new ``marks_entered`` flag on the line (set by UI
  onchange AND by any direct/bulk write of ``marks_obtained``) and blocks
  publishing while any attended applicant is missing marks.
- Venue/time overlap constraint (same venue, same date, overlapping hours).
- ``marks_entered`` is also set on bulk/API writes so the guard cannot be
  bypassed through non-UI paths. The existing ``_check_marks_obtained``
  constraint is left untouched.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EntranceTestPrecisionExt(models.Model):
    _inherit = 'oacis.admission.entrance.test'

    def action_publish_results(self):
        for record in self:
            if record.state != 'completed':
                raise UserError(_(
                    'Test must be completed before publishing results.',
                ))
            for line in record.applicant_line_ids:
                if line.attended and not line.marks_entered:
                    raise UserError(_(
                        'Please enter marks for all attended applicants '
                        'before publishing.',
                    ))
                if line.applicant_id.state == 'entrance_scheduled':
                    if line.attended:
                        line.applicant_id.entrance_score = line.marks_obtained
                        line.applicant_id.action_add_to_merit()
                    else:
                        line.applicant_id.write({
                            'state': 'rejected',
                            'rejection_reason': _(
                                'Did not attend entrance test.',
                            ),
                        })
            record.write({'state': 'result_published'})

    @api.constrains('test_date', 'start_time', 'end_time', 'venue')
    def _check_venue_overlap(self):
        for record in self:
            overlapping = self.search([
                ('id', '!=', record.id),
                ('venue', '=', record.venue),
                ('test_date', '=', record.test_date),
                ('company_id', '=', record.company_id.id),
            ])
            for other in overlapping:
                if (record.start_time < other.end_time
                        and other.start_time < record.end_time):
                    raise ValidationError(_(
                        'Venue "%s" is already booked for another entrance '
                        'test on %s overlapping this time.',
                    ) % (record.venue, record.test_date))


class EntranceTestLinePrecisionExt(models.Model):
    _inherit = 'oacis.admission.entrance.test.line'

    marks_entered = fields.Boolean(
        string='Marks Entered', default=False,
        help='True once marks were entered for this applicant, whether via the '
             'UI onchange or a direct/bulk write of Marks Obtained.',
    )

    @api.onchange('marks_obtained')
    def _onchange_marks_obtained(self):
        for record in self:
            record.marks_entered = True

    def write(self, vals):
        if 'marks_obtained' in vals:
            vals['marks_entered'] = True
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'marks_obtained' in vals:
                vals['marks_entered'] = True
        return super().create(vals_list)
