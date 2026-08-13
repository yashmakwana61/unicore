from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UniCoreProgressionRecord(models.Model):
    _name = 'unicore.progression.record'
    _description = 'Student Progression Record'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'student_id, academic_year_id desc'
    _check_company_auto = True
    _rec_name = 'name'

    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='student_id.company_id',
        store=True,
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='unicore.academic.year',
        string='Academic Year',
        required=True,
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        domain="[('academic_year_id', '=', academic_year_id)]",
        help='Optional: specific semester if progression is run mid-year.',
        tracking=True,
    )

    cgpa_snapshot = fields.Float(
        string='CGPA Snapshot',
        digits=(4, 2),
        readonly=True,
    )
    credits_earned_snapshot = fields.Float(
        string='Credits Earned Snapshot',
        digits=(5, 1),
        readonly=True,
    )

    decision = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('promoted', 'Promoted'),
            ('repeat', 'Repeat'),
            ('probation', 'Academic Probation'),
            ('dismissed', 'Dismissed'),
        ],
        string='Progression Decision',
        default='pending',
        required=True,
        tracking=True,
    )
    decided_by = fields.Many2one(
        comodel_name='res.users',
        string='Decided By',
        readonly=True,
    )
    decision_date = fields.Date(
        string='Decision Date',
        readonly=True,
    )
    notes = fields.Text(string='Internal Notes')

    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('student_id', 'academic_year_id')
    def _compute_name(self):
        for rec in self:
            student_name = rec.student_id.display_name if rec.student_id else 'Unknown'
            year_name = rec.academic_year_id.display_name if rec.academic_year_id else 'Unknown'
            rec.name = f"{student_name} - {year_name} Progression"

    @api.onchange('student_id')
    def _onchange_student_id(self):
        if self.student_id:
            self.cgpa_snapshot = self.student_id.cgpa
            self.credits_earned_snapshot = self.student_id.total_credits_earned

    def _post_decision_message(self, decision):
        self.ensure_one()
        msg = _('Progression decision recorded: <strong>%s</strong>.') % dict(self._fields['decision'].selection).get(decision, decision)
        self.message_post(body=msg)

    def action_promote(self):
        self.ensure_one()
        self.write({
            'decision': 'promoted',
            'decided_by': self.env.user.id,
            'decision_date': fields.Date.today(),
        })
        self._post_decision_message('promoted')

    def action_repeat(self):
        self.ensure_one()
        self.write({
            'decision': 'repeat',
            'decided_by': self.env.user.id,
            'decision_date': fields.Date.today(),
        })
        self._post_decision_message('repeat')

    def action_probation(self):
        self.ensure_one()
        self.write({
            'decision': 'probation',
            'decided_by': self.env.user.id,
            'decision_date': fields.Date.today(),
        })
        self._post_decision_message('probation')

    def action_dismiss(self):
        self.ensure_one()
        self.write({
            'decision': 'dismissed',
            'decided_by': self.env.user.id,
            'decision_date': fields.Date.today(),
        })
        self._post_decision_message('dismissed')

    @api.constrains('decision', 'decided_by', 'decision_date')
    def _check_decision_fields(self):
        for record in self:
            if record.decision != 'pending' and not record.decided_by:
                raise ValidationError(_('A decision must have an associated user (Decided By).'))
            if record.decision != 'pending' and not record.decision_date:
                raise ValidationError(_('A decision must have a Decision Date.'))
