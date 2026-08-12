import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FacultyQualification(models.Model):
    _name = 'unicore.faculty.qualification'
    _description = 'Faculty Academic Qualification'
    _order = 'faculty_member_id, qualification_level desc'

    faculty_member_id = fields.Many2one(
        'unicore.faculty.member',
        string='Faculty Member',
        required=True,
        ondelete='cascade',
    )
    qualification_level = fields.Selection([
        ('bachelors', "Bachelor's Degree"),
        ('masters', "Master's Degree"),
        ('mphil', 'M.Phil'),
        ('phd', 'PhD / Doctorate'),
        ('postdoc', 'Post-Doctoral'),
        ('professional', 'Professional Certification'),
        ('diploma', 'Diploma'),
        ('other', 'Other'),
    ], string='Qualification Level', required=True)
    degree_title = fields.Char(
        string='Degree / Certification Title',
        required=True,
        help='e.g. PhD in Computer Science',
    )
    field_of_study = fields.Char(string='Field of Study', required=True)
    institution_name = fields.Char(string='Institution / University', required=True)
    country_id = fields.Many2one('res.country', string='Country')
    year_of_completion = fields.Integer(string='Year of Completion', required=True)
    grade_or_cgpa = fields.Char(string='Grade / CGPA')
    is_highest = fields.Boolean(
        string='Highest Qualification',
        default=False,
        help='Mark as highest academic qualification',
    )
    certificate_file = fields.Binary(string='Certificate', attachment=True)
    is_verified = fields.Boolean(string='Verified', default=False)

    @api.constrains('year_of_completion')
    def _check_year_of_completion(self):
        current_year = date.today().year
        for record in self:
            if record.year_of_completion < 1950 or record.year_of_completion > current_year:
                raise ValidationError(_(
                    'Year of completion must be between 1950 and %(year)d.',
                    year=current_year,
                ))

    @api.constrains('is_highest', 'faculty_member_id')
    def _check_unique_highest(self):
        for record in self:
            if record.is_highest:
                existing = self.search([
                    ('faculty_member_id', '=', record.faculty_member_id.id),
                    ('is_highest', '=', True),
                    ('id', '!=', record.id),
                ])
                if existing:
                    raise ValidationError(_(
                        'Only one qualification per faculty member can be marked as highest.',
                    ))
