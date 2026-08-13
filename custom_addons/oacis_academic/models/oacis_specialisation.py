import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UnicoreSpecialisation(models.Model):
    """Program Specialisation or Major representing a branch of study."""

    _name = 'unicore.specialisation'
    _description = 'Program Specialisation or Major'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'program_id, sequence, name'
    _check_company_auto = True

    name = fields.Char(
        string='Specialisation Name',
        required=True,
        translate=True,
        help='e.g. Artificial Intelligence, Finance, Civil Structures',
    )
    code = fields.Char(
        string='Specialisation Code',
        required=True,
        size=20,
    )
    program_id = fields.Many2one(
        comodel_name='unicore.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    department_id = fields.Many2one(
        comodel_name='unicore.department',
        related='program_id.department_id',
        string='Department',
        store=True,
        readonly=True,
    )
    faculty_id = fields.Many2one(
        comodel_name='unicore.faculty',
        related='program_id.faculty_id',
        string='Faculty',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='program_id.company_id',
        string='Institution',
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    min_credits = fields.Integer(
        string='Minimum Credits for Specialisation',
        default=30,
    )
    description = fields.Text(
        string='Description',
    )
    is_default = fields.Boolean(
        string='Is Default Specialisation',
        default=False,
        help='Students not selecting a specialisation are assigned here',
    )

    _unique_spec_code_program = models.Constraint(
        'UNIQUE(code, program_id)',
        'Specialisation code must be unique per program.',
    )

    @api.constrains('is_default', 'program_id')
    def _check_unique_default(self):
        for record in self:
            if record.is_default:
                existing = self.search([
                    ('program_id', '=', record.program_id.id),
                    ('is_default', '=', True),
                    ('id', '!=', record.id),
                ])
                if existing:
                    raise ValidationError(
                        _('Only one default specialisation is allowed per program.'),
                    )
