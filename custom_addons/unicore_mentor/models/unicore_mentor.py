from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MentorAllocation(models.Model):
    _name = 'unicore.mentor.allocation'
    _description = 'Mentor Allocation'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc, mentor_id'
    _check_company_auto = True
    _rec_name = 'name'

    mentor_id = fields.Many2one(
        'unicore.faculty.member',
        string='Mentor (Faculty)',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='mentor_id.company_id',
        store=True,
    )
    academic_year_id = fields.Many2one(
        'unicore.academic.year',
        string='Academic Year',
        required=True,
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    student_ids = fields.Many2many(
        'unicore.student',
        'unicore_mentor_student_rel',
        'allocation_id', 'student_id',
        string='Mentees',
        domain="[('company_id', '=', company_id)]",
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('done', 'Done')
    ], string='Status', default='draft', required=True, tracking=True)
    
    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('mentor_id', 'academic_year_id')
    def _compute_name(self):
        for rec in self:
            mentor_name = rec.mentor_id.display_name if rec.mentor_id else 'Unknown'
            year_name = rec.academic_year_id.display_name if rec.academic_year_id else 'Unknown'
            rec.name = f"Mentorship: {mentor_name} ({year_name})"

    def action_activate(self):
        self.write({'state': 'active'})

    def action_done(self):
        self.write({'state': 'done'})


class MentorMeetingLog(models.Model):
    _name = 'unicore.mentor.meeting.log'
    _description = 'Mentor Meeting Log'
    _inherit = ['unicore.mixin']
    _order = 'meeting_date desc'
    _check_company_auto = True
    _rec_name = 'meeting_date'

    allocation_id = fields.Many2one(
        'unicore.mentor.allocation',
        string='Mentorship Allocation',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='allocation_id.company_id',
        store=True,
    )
    student_id = fields.Many2one(
        'unicore.student',
        string='Student',
        required=True,
        domain="[('id', 'in', student_ids)]"
    )
    student_ids = fields.Many2many(
        related='allocation_id.student_ids',
        string='Available Students'
    )
    meeting_date = fields.Date(
        string='Meeting Date',
        required=True,
        default=fields.Date.today,
    )
    notes = fields.Text(string='Meeting Notes', required=True)
    follow_up_required = fields.Boolean(string='Follow Up Required', default=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('completed', 'Completed')
    ], string='Status', default='draft', required=True)

    @api.constrains('meeting_date')
    def _check_meeting_date(self):
        for record in self:
            if record.meeting_date and record.meeting_date > fields.Date.today():
                raise ValidationError(_('Meeting date cannot be in the future.'))

    def action_complete(self):
        self.write({'state': 'completed'})
