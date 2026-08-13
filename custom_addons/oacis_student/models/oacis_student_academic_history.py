from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OacisStudentAcademicHistory(models.Model):
    """Academic history records storing past enrollments, year/semester results."""

    _name = 'oacis.student.academic.history'
    _description = 'Student Academic History'
    _inherit = ['oacis.mixin', 'mail.thread']
    _order = 'academic_year_id desc, semester_id desc'
    _check_company_auto = True
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name', compute='_compute_display_name', store=True,
    )

    student_id = fields.Many2one(
        comodel_name='oacis.student', string='Student',
        required=True, ondelete='cascade',
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        related='student_id.company_id', store=True, readonly=True,
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus', string='Campus',
        related='student_id.campus_id', store=True, readonly=True,
    )

    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year', string='Academic Year',
        required=True,
    )
    semester_id = fields.Many2one(
        comodel_name='oacis.semester', string='Semester',
        domain="[('academic_year_id', '=', academic_year_id)]",
        required=True,
    )
    year_of_study = fields.Integer(
        string='Year of Study', required=True,
        help='Which year level this record belongs to (1, 2, 3, ...)',
    )

    semester_gpa = fields.Float(string='Semester GPA', digits=(4, 2), default=0.0)
    cumulative_gpa = fields.Float(
        string='Cumulative GPA After This Sem',
        digits=(4, 2), default=0.0,
    )
    credits_attempted = fields.Integer(string='Credits Attempted', default=0)
    credits_earned = fields.Integer(string='Credits Earned', default=0)
    total_subjects = fields.Integer(string='Total Subjects', default=0)
    subjects_passed = fields.Integer(string='Subjects Passed', default=0)
    subjects_failed = fields.Integer(string='Subjects Failed', compute='_compute_failed', store=True)

    grade_summary = fields.Text(string='Grade Summary')
    remarks = fields.Text(string='Remarks')
    is_current = fields.Boolean(string='Current Enrollment', default=False)

    enrollment_state = fields.Selection(
        selection=[
            ('registered', 'Registered'),
            ('continuing', 'Continuing'),
            ('completed', 'Completed'),
            ('discontinued', 'Discontinued'),
        ],
        string='Enrollment State', default='completed',
    )

    @api.depends('academic_year_id', 'semester_id', 'student_id')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.student_id:
                parts.append(record.student_id.display_name)
            if record.semester_id:
                parts.append(record.semester_id.name)
            elif record.academic_year_id:
                parts.append(record.academic_year_id.name)
            record.display_name = ' — '.join(parts) if parts else 'N/A'

    @api.depends('subjects_passed', 'total_subjects')
    def _compute_failed(self):
        for record in self:
            record.subjects_failed = record.total_subjects - record.subjects_passed

    @api.constrains('credits_earned', 'credits_attempted')
    def _check_credits(self):
        for record in self:
            if record.credits_earned > record.credits_attempted:
                raise ValidationError(
                    _('Credits earned (%(earned)d) cannot exceed credits attempted (%(attempted)d).',
                      earned=record.credits_earned, attempted=record.credits_attempted),
                )

    @api.constrains('semester_gpa', 'cumulative_gpa')
    def _check_gpa_range(self):
        for record in self:
            if record.semester_gpa < 0.0 or record.semester_gpa > 4.0:
                raise ValidationError(
                    _('Semester GPA must be between 0.0 and 4.0 for record %s.') % record.display_name,
                )

    _unique_student_semester = models.Constraint(
        'UNIQUE(student_id, semester_id)',
        'Academic history for this semester already exists for this student.',
    )
