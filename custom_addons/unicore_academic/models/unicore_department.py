import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UnicoreDepartment(models.Model):
    """Academic Department within a Faculty."""

    _name = 'unicore.department'
    _description = 'Academic Department'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'faculty_id, sequence, name'
    _check_company_auto = True

    name = fields.Char(
        string='Department Name',
        required=True,
        translate=True,
        help='e.g. Department of Computer Science',
    )
    code = fields.Char(
        string='Department Code',
        required=True,
        size=10,
        help='e.g. CS, MECH, MBA, PHY',
    )
    faculty_id = fields.Many2one(
        comodel_name='unicore.faculty',
        string='Faculty',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='faculty_id.company_id',
        string='Institution',
        store=True,
        readonly=True,
    )
    hod_id = fields.Many2one(
        comodel_name='res.users',
        string='Head of Department',
        help='HOD responsible for this department',
        tracking=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    campus_ids = fields.Many2many(
        comodel_name='unicore.campus',
        relation='unicore_department_campus_rel',
        column1='department_id',
        column2='campus_id',
        string='Campuses',
        help='Campuses where this department operates',
    )
    program_ids = fields.One2many(
        comodel_name='unicore.program',
        inverse_name='department_id',
        string='Programs',
    )
    program_count = fields.Integer(
        string='Total Programs',
        compute='_compute_program_count',
        store=True,
    )
    dept_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Operational'),
            ('suspended', 'Suspended'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    description = fields.Html(
        string='About Department',
    )
    established_year = fields.Integer(
        string='Established Year',
    )
    email = fields.Char(
        string='Department Email',
    )
    phone = fields.Char(
        string='Department Phone',
    )

    _unique_dept_code_faculty = models.Constraint(
        'UNIQUE(code, faculty_id)',
        'Department code must be unique per faculty.',
    )

    @api.depends('program_ids')
    def _compute_program_count(self):
        for record in self:
            record.program_count = len(record.program_ids)

    @api.constrains('code')
    def _check_code_uppercase_alphanumeric(self):
        for record in self:
            if record.code:
                if not record.code.isalnum():
                    raise ValidationError(
                        _('Department code must be uppercase alphanumeric only.'),
                    )
                if record.code != record.code.upper():
                    raise ValidationError(
                        _('Department code must be uppercase only.'),
                    )

    @api.constrains('established_year')
    def _check_established_year(self):
        current_year = date.today().year
        for record in self:
            if record.established_year and (
                record.established_year < 1800 or record.established_year > current_year
            ):
                raise ValidationError(
                    _('Established year must be between 1800 and %(year)s.', year=current_year),
                )

    def action_set_operational(self):
        self.ensure_one()
        if not self.program_ids:
            raise UserError(
                _('You must add at least one program before setting the department to Operational.'),
            )
        self.dept_state = 'active'

    def action_suspend(self):
        self.ensure_one()
        self.dept_state = 'suspended'

    def action_close(self):
        self.ensure_one()
        self.dept_state = 'closed'

    def action_reset_draft(self):
        self.ensure_one()
        self.dept_state = 'draft'

    def action_open_programs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Programs'),
            'res_model': 'unicore.program',
            'view_mode': 'kanban,list,form',
            'domain': [('department_id', '=', self.id)],
            'context': {'default_department_id': self.id},
        }
