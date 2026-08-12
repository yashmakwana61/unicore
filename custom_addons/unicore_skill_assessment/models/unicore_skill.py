from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Skill(models.Model):
    _name = 'unicore.skill'
    _description = 'Skill'
    _inherit = ['unicore.mixin']
    _order = 'category, name'
    _check_company_auto = True

    name = fields.Char(string='Skill Name', required=True)
    category = fields.Selection([
        ('technical', 'Technical'),
        ('soft', 'Soft Skill'),
        ('language', 'Language'),
        ('other', 'Other'),
    ], string='Category', required=True, default='technical')
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)


class StudentSkillAssessment(models.Model):
    _name = 'unicore.student.skill.assessment'
    _description = 'Student Skill Assessment'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date_assessed desc'
    _check_company_auto = True
    _rec_name = 'name'

    student_id = fields.Many2one(
        'unicore.student',
        string='Student',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='student_id.company_id',
        store=True,
    )
    skill_id = fields.Many2one(
        'unicore.skill',
        string='Skill',
        required=True,
        domain="[('company_id', 'in', [company_id, False])]",
        tracking=True,
    )
    assessed_by_id = fields.Many2one(
        'unicore.faculty.member',
        string='Assessed By',
        required=True,
    )
    proficiency_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ], string='Proficiency Level', required=True, tracking=True)
    date_assessed = fields.Date(
        string='Date Assessed',
        required=True,
        default=fields.Date.today,
    )
    comments = fields.Text(string='Comments')

    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('student_id', 'skill_id', 'proficiency_level')
    def _compute_name(self):
        for rec in self:
            student_name = rec.student_id.display_name if rec.student_id else 'Unknown'
            skill_name = rec.skill_id.name if rec.skill_id else 'Unknown'
            level_dict = dict(rec._fields['proficiency_level'].selection)
            level_name = level_dict.get(rec.proficiency_level, 'Unknown')
            rec.name = f"{student_name} - {skill_name} ({level_name})"

    @api.constrains('date_assessed')
    def _check_date_assessed(self):
        for record in self:
            if record.date_assessed and record.date_assessed > fields.Date.today():
                raise ValidationError(_('Assessment date cannot be in the future.'))
