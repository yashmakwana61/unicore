from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class UnicoreAcademicUnit(models.Model):
    """Generic self-referencing academic unit tree.

    Replaces the rigid Faculty -> Department -> Program chain for non-university
    institution types. Depth-unlimited and type-configurable:

        unicore.academic.unit
          - name, code
          - unit_type_id  (configurable taxonomy, e.g. faculty | department |
                           grade_level | stream | wing | division | batch_group)
          - parent_id     (self-referencing, nullable)
          - child_ids
          - company_id

    The terminal node that students actually enroll into (program / cohort /
    batch) is a separate concept and attaches to this tree in Phase 1 via
    unicore.program.academic_unit_id.
    """

    _name = 'unicore.academic.unit'
    _description = 'Academic Unit'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'parent_id, sequence, name'
    _check_company_auto = True
    _rec_name = 'display_name'

    name = fields.Char(
        string='Unit Name',
        required=True,
        translate=True,
        tracking=True,
        help='e.g. Faculty of Engineering, Grade 5, Morning Wing',
    )
    code = fields.Char(
        string='Unit Code',
        required=True,
        size=20,
        tracking=True,
        help='Short unique code e.g. ENG, G5, WING-M',
    )
    unit_type_id = fields.Many2one(
        comodel_name='unicore.academic.unit.type',
        string='Unit Type',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    parent_id = fields.Many2one(
        comodel_name='unicore.academic.unit',
        string='Parent Unit',
        ondelete='cascade',
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    child_ids = fields.One2many(
        comodel_name='unicore.academic.unit',
        inverse_name='parent_id',
        string='Child Units',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )
    head_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Head / In-Charge',
        help='Person responsible for this unit (Dean, HOD, Section Head, Wing In-Charge...)',
        tracking=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    allowed_child_type_ids = fields.Many2many(
        comodel_name='unicore.academic.unit.type',
        related='unit_type_id.allowed_child_type_ids',
        string='Allowed Child Types',
        readonly=True,
        help='Unit types that may nest directly under a unit of this type.',
    )
    unit_count = fields.Integer(
        string='Child Unit Count',
        compute='_compute_unit_count',
        store=True,
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        recursive=True,
    )
    path = fields.Char(
        string='Hierarchy Path',
        compute='_compute_path',
        recursive=True,
        help='Full dotted path from the root unit to this unit.',
    )

    _unique_unit_code_company = models.Constraint(
        'UNIQUE(code, company_id)',
        'Unit code must be unique per institution.',
    )

    @api.depends('child_ids')
    def _compute_unit_count(self):
        for record in self:
            record.unit_count = len(record.child_ids)

    @api.depends('name', 'code', 'unit_type_id.name', 'parent_id.display_name')
    def _compute_display_name(self):
        for record in self:
            type_name = record.unit_type_id.name or ''
            record.display_name = '%s (%s)' % (record.name, type_name) if type_name else record.name

    @api.depends('parent_id.path', 'name')
    def _compute_path(self):
        for record in self:
            parts = []
            node = record
            seen = set()
            while node:
                if node.id in seen:
                    break
                seen.add(node.id)
                parts.append(node.name)
                node = node.parent_id
            record.path = ' / '.join(reversed(parts)) if parts else record.name

    @api.constrains('parent_id', 'unit_type_id', 'id')
    def _check_parent_type(self):
        """Ensure the parent unit's type allows this unit's type as a child.

        When the parent type declares an explicit allow-list and this unit's type
        is not in it, reject. An empty allow-list means 'any type is allowed'.
        """
        for record in self:
            if not record.parent_id:
                continue
            allowed = record.parent_id.allowed_child_type_ids
            if allowed and record.unit_type_id not in allowed:
                raise ValidationError(
                    _('A "%(child)s" unit cannot be created under a '
                      '"%(parent)s" unit. Allowed child types: %(allowed)s.',
                      child=record.unit_type_id.name,
                      parent=record.parent_id.unit_type_id.name,
                      allowed=', '.join(allowed.mapped('name')) or _('any'),
                    )
                )

    @api.constrains('parent_id', 'id')
    def _check_no_cycle(self):
        """Prevent a unit from being its own ancestor (cycle detection)."""
        for record in self:
            node = record.parent_id
            seen = {record.id}
            while node:
                if node.id in seen:
                    raise ValidationError(
                        _('Cannot set "%(name)s" as parent — this would create '
                          'a circular hierarchy.',
                          name=record.parent_id.name or '')
                    )
                seen.add(node.id)
                node = node.parent_id

    def action_open_children(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Child Units'),
            'res_model': 'unicore.academic.unit',
            'view_mode': 'list,form,kanban',
            'domain': [('parent_id', '=', self.id)],
            'context': {
                'default_parent_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }
