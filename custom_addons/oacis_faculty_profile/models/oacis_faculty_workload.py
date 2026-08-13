import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FacultyWorkload(models.Model):
    _name = 'unicore.faculty.workload'
    _description = 'Faculty Teaching Workload Record'
    _order = 'faculty_member_id, academic_year_id, semester_id'
    _check_company_auto = True

    faculty_member_id = fields.Many2one(
        'unicore.faculty.member',
        string='Faculty Member',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='faculty_member_id.company_id',
        store=True,
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        'unicore.academic.year',
        string='Academic Year',
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    semester_id = fields.Many2one(
        'unicore.semester',
        string='Semester',
        required=True,
        domain="[('academic_year_id', '=', academic_year_id)]",
    )
    program_id = fields.Many2one('unicore.program', string='Program')
    course_name = fields.Char(
        string='Course / Subject Name',
        required=True,
        help='Will link to unicore.course in future module',
    )
    course_code = fields.Char(string='Course Code')
    weekly_hours = fields.Float(
        string='Weekly Teaching Hours',
        required=True,
        default=3.0,
        digits=(4, 1),
    )
    student_count = fields.Integer(string='Enrolled Students', default=0)
    room_id = fields.Many2one('unicore.room', string='Assigned Room')
    workload_type = fields.Selection([
        ('teaching', 'Teaching'),
        ('lab', 'Laboratory'),
        ('tutorial', 'Tutorial'),
        ('seminar', 'Seminar'),
        ('thesis_supervision', 'Thesis Supervision'),
        ('research', 'Research'),
        ('administrative', 'Administrative'),
    ], string='Workload Type', default='teaching', required=True)

    _unique_workload_course_faculty_semester = models.Constraint(
        'UNIQUE(faculty_member_id, course_code, semester_id)',
        'Duplicate course assignment for this faculty in semester.',
    )

    @api.constrains('weekly_hours')
    def _check_weekly_hours(self):
        for record in self:
            if record.weekly_hours <= 0 or record.weekly_hours > 30:
                raise ValidationError(_('Weekly teaching hours must be greater than 0 and at most 30.'))

    @api.constrains('student_count')
    def _check_student_count(self):
        for record in self:
            if record.student_count < 0:
                raise ValidationError(_('Student count cannot be negative.'))
