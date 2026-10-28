"""Edicai Demo — demo profile configuration.

``edicai.demo.profile`` maps each supported ``institution_type`` (the exact
selection driven by ``edicai.institution.profile``) to small, fast, dashboard-
meaningful record volumes.  Adding a future institution type means adding one
profile record + one dataset entry — no engine rewrite.
"""

from odoo import fields, models


class EdicaiDemoProfile(models.Model):
    _name = 'edicai.demo.profile'
    _description = 'Demo Data Profile'
    _order = 'sequence, name'

    name = fields.Char(string='Profile Name', required=True)
    code = fields.Char(string='Profile Code', required=True, size=20)
    sequence = fields.Integer(string='Sequence', default=10)
    institution_type = fields.Selection(
        selection=[
            ('university', 'University'),
            ('college', 'College'),
            ('school', 'K-12 School'),
            ('training', 'Training Institute'),
            ('academy', 'Academy / Test-Prep'),
            ('coaching', 'Coaching Center'),
        ],
        string='Institution Type',
        required=True,
    )
    description = fields.Text(string='Description')

    # --- Volumes (small & fast defaults; editable per profile) ---
    faculty_count = fields.Integer(string='Faculty / Trainers', default=6)
    staff_count = fields.Integer(string='Admin Staff', default=1)
    student_count = fields.Integer(string='Students / Learners', default=60)
    course_count = fields.Integer(string='Courses / Subjects', default=8)
    guardian_every_n = fields.Integer(
        string='Guardian Every N Students',
        default=2,
        help='Create one guardian for every N students. 0 disables guardians.',
    )
    attendance_sessions_per_offering = fields.Integer(
        string='Attendance Sessions / Offering', default=2)
    applicants_count = fields.Integer(string='Admission Applicants', default=6)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('unique_demo_profile_code',
         'UNIQUE(code)',
         'A demo profile with this code already exists.'),
        ('unique_demo_profile_type',
         'UNIQUE(institution_type)',
         'A demo profile for this institution type already exists.'),
    ]

    def action_generate_demo(self):
        """Open the demo wizard prefilled with this profile."""
        self.ensure_one()
        wizard = self.env['edicai.demo.generate.wizard'].create({
            'demo_profile_id': self.id,
        })
        wizard._onchange_company_id()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Demo Data',
            'res_model': 'edicai.demo.generate.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
