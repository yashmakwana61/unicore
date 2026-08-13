import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UnicoreFaculty(models.Model):
    """Academic Faculty representing a School or College within a University."""

    _name = 'unicore.faculty'
    _description = 'Academic Faculty (School/College within University)'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _check_company_auto = True

    name = fields.Char(
        string='Faculty Name',
        required=True,
        translate=True,
        help='e.g. Faculty of Engineering, School of Business',
    )
    code = fields.Char(
        string='Faculty Code',
        required=True,
        size=10,
        help='Short unique code e.g. ENG, BUS, SCI',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )
    campus_ids = fields.Many2many(
        comodel_name='unicore.campus',
        relation='unicore_faculty_campus_rel',
        column1='faculty_id',
        column2='campus_id',
        string='Campuses',
        help='Campuses where this faculty operates',
        domain='[("company_id", "=", company_id)]',
    )
    dean_id = fields.Many2one(
        comodel_name='res.users',
        string='Dean',
        help='Dean or Head of Faculty',
        tracking=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    department_ids = fields.One2many(
        comodel_name='unicore.department',
        inverse_name='faculty_id',
        string='Departments',
    )
    department_count = fields.Integer(
        string='Total Departments',
        compute='_compute_department_count',
        store=True,
    )
    program_count = fields.Integer(
        string='Total Programs',
        compute='_compute_program_count',
        store=False,
    )
    faculty_state = fields.Selection(
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
        string='About Faculty',
        help='Public description of the faculty',
    )
    established_year = fields.Integer(
        string='Established Year',
    )
    image = fields.Binary(
        string='Faculty Image',
        attachment=True,
    )

    _unique_faculty_code_company = models.Constraint(
        'UNIQUE(code, company_id)',
        'Faculty code must be unique per institution.',
    )

    @api.depends('department_ids')
    def _compute_department_count(self):
        for record in self:
            record.department_count = len(record.department_ids)

    def _compute_program_count(self):
        program_model = self.env['unicore.program']
        for record in self:
            record.program_count = program_model.search_count(
                [('faculty_id', '=', record.id)],
            )

    @api.constrains('code')
    def _check_code_uppercase_alpha(self):
        for record in self:
            if record.code:
                if not record.code.isalpha():
                    raise ValidationError(
                        _('Faculty code must contain only letters (no numbers or special characters).'),
                    )
                if record.code != record.code.upper():
                    raise ValidationError(
                        _('Faculty code must be uppercase only.'),
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
        if not self.department_ids:
            raise UserError(
                _('You must add at least one department before setting the faculty to Operational.'),
            )
        self.faculty_state = 'active'

    def action_suspend(self):
        self.ensure_one()
        self.faculty_state = 'suspended'

    def action_close(self):
        self.ensure_one()
        self.faculty_state = 'closed'

    def action_reset_draft(self):
        self.ensure_one()
        self.faculty_state = 'draft'

    def action_open_departments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Departments'),
            'res_model': 'unicore.department',
            'view_mode': 'list,form',
            'domain': [('faculty_id', '=', self.id)],
            'context': {'default_faculty_id': self.id},
        }

    def action_open_programs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Programs'),
            'res_model': 'unicore.program',
            'view_mode': 'kanban,list,form',
            'domain': [('faculty_id', '=', self.id)],
            'context': {'default_faculty_id': self.id},
        }
