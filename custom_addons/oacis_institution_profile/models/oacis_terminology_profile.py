from odoo import api, fields, models


class OacisTerminologyProfile(models.Model):
    """Field-label substitution layer for entity-specific terminology.

    Cosmetic only - no model or field names change. Each term maps the generic
    Oacis vocabulary to the institution's vocabulary, or hides the concept by
    leaving it blank. Applied at institution setup time (one-time relabeling,
    Phase 5), per the locked product decision.
    """

    _name = 'oacis.terminology.profile'
    _description = 'Terminology Profile'
    _inherit = ['oacis.mixin']
    _order = 'name'

    # concept -> (term field name, generic fallback label)
    _TERM_CONCEPTS = {
        'faculty': ('term_faculty', 'Faculty'),
        'department': ('term_department', 'Department'),
        'program': ('term_program', 'Program'),
        'student': ('term_student', 'Student'),
        'faculty_staff': ('term_faculty_staff', 'Faculty / Staff'),
        'semester': ('term_semester', 'Semester'),
        'academic_year': ('term_academic_year', 'Academic Year'),
    }

    name = fields.Char(
        string='Profile Name',
        required=True,
        help='e.g. University (Legacy), K-12 School, Training Institute',
    )
    code = fields.Char(
        string='Profile Code',
        required=True,
        size=20,
        help='Short unique code e.g. UNI_LEGACY, K12, TRAINING',
    )
    term_faculty = fields.Char(
        string='Faculty Label',
        help='e.g. "Faculty", "Wing", "Division". Blank = hide the concept.',
    )
    term_department = fields.Char(
        string='Department Label',
        help='e.g. "Department", "Grade Level". Blank = hide the concept.',
    )
    term_program = fields.Char(
        string='Program Label',
        help='e.g. "Program", "Class/Section", "Batch", "Course Track".',
    )
    term_student = fields.Char(
        string='Student Label',
        help='e.g. "Student", "Learner", "Trainee".',
    )
    term_faculty_staff = fields.Char(
        string='Faculty / Staff Label',
        help='e.g. "Faculty", "Teacher", "Trainer", "Instructor".',
    )
    term_semester = fields.Char(
        string='Semester Label',
        help='e.g. "Semester", "Term", "Cycle".',
    )
    term_academic_year = fields.Char(
        string='Academic Year Label',
        help='e.g. "Academic Year", "Session".',
    )
    description = fields.Text(
        string='Description',
    )
    label_summary = fields.Char(
        string='Applied Labels',
        compute='_compute_label_summary',
        help='Read-only preview of the labels this profile applies. A blank '
             'term keeps the generic label.',
    )

    _unique_terminology_code = models.Constraint(
        'UNIQUE(code)',
        'A terminology profile with this code already exists.',
    )

    def resolve_label(self, concept, default=None):
        """Resolve the effective label for a concept.

        Returns the profile's substituted label, or ``default`` (or the generic
        English term) when the substitution is blank. Unknown concepts resolve
        to ``default`` or the concept key.
        """
        self.ensure_one()
        field_name, generic = self._TERM_CONCEPTS.get(concept, (None, None))
        if not field_name:
            return default or concept
        return getattr(self, field_name) or default or generic

    @api.depends(
        'term_faculty', 'term_department', 'term_program', 'term_student',
        'term_faculty_staff', 'term_semester', 'term_academic_year',
    )
    def _compute_label_summary(self):
        for record in self:
            parts = [
                '%s → %s' % (generic, getattr(record, field) or generic)
                for field, generic in record._TERM_CONCEPTS.values()
            ]
            record.label_summary = ' · '.join(parts)
