from odoo import fields, models


class OacisStudentStatusWizard(models.TransientModel):
    """Wizard for student status transitions that require a reason."""

    _name = 'oacis.student.status.wizard'
    _description = 'Student Status Change Wizard'

    student_id = fields.Many2one(
        comodel_name='oacis.student', string='Student',
        required=True, readonly=True,
    )
    current_state = fields.Selection(
        related='student_id.student_state', string='Current Status',
        readonly=True,
    )
    target_state = fields.Selection(
        selection=[
            ('on_leave', 'On Leave'),
            ('withdrawn', 'Withdrawn'),
            ('expelled', 'Expelled'),
            ('admitted', 'Re-admitted'),
        ],
        string='Target Status', required=True,
        readonly=True,
    )
    reason = fields.Text(string='Reason', required=True)
    date = fields.Date(
        string='Status Change Date', required=True,
        default=fields.Date.today,
    )

    def action_confirm(self):
        self.ensure_one()
        record = self.student_id

        old = self.current_state
        record.write({
            'student_state': self.target_state,
            'status_change_date': self.date,
            'status_change_reason': self.reason,
        })
        record._post_status_message(old, self.target_state, self.reason)
        return {'type': 'ir.actions.act_window_close'}
