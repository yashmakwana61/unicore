from odoo import _, api, fields, models


class OacisStudentEnrollmentExt(models.Model):
    _inherit = 'oacis.student'

    enrollment_ids = fields.One2many(
        comodel_name='oacis.enrollment',
        inverse_name='student_id',
        string='Enrollments',
    )

    active_enrollment_count = fields.Integer(
        string='Active Enrollments',
        compute='_compute_active_enrollment_count',
    )

    total_credits_this_semester = fields.Float(
        string='Credits This Semester',
        compute='_compute_credits_this_semester',
        digits=(5, 1),
    )

    @api.depends('enrollment_ids', 'enrollment_ids.enrollment_state')
    def _compute_active_enrollment_count(self):
        for rec in self:
            rec.active_enrollment_count = len(
                rec.enrollment_ids.filtered(
                    lambda e: e.enrollment_state == 'registered',
                ),
            )

    @api.depends('enrollment_ids', 'enrollment_ids.enrollment_state',
                 'enrollment_ids.credit_hours', 'current_semester_id')
    def _compute_credits_this_semester(self):
        for rec in self:
            if not rec.current_semester_id:
                rec.total_credits_this_semester = 0.0
                continue
            active = rec.enrollment_ids.filtered(
                lambda e: (
                    e.enrollment_state == 'registered'
                    and e.semester_id == rec.current_semester_id
                ),
            )
            rec.total_credits_this_semester = sum(
                e.credit_hours for e in active
            )

    def action_open_enrollments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enrollments'),
            'res_model': 'oacis.enrollment',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {
                'default_student_id': self.id,
            },
        }
