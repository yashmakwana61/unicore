"""Oacis Demo — generation wizard (TransientModel).

Single entry point for the institution-aware demo system::

    Generate Demo Data  -> detect institution type -> build matching dataset
    Reset Demo Data     -> remove only generator-created rows for the company

Safe to open repeatedly; generation refuses to duplicate without reset.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class OacisDemoGenerateWizard(models.TransientModel):
    _name = 'oacis.demo.generate.wizard'
    _description = 'Generate Institution Demo Data'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        help='Demo data is generated only for this institution.',
    )
    institution_type = fields.Char(
        string='Detected Institution Type',
        compute='_compute_institution_type',
        help='Resolved from the institution profile on the company.',
    )
    demo_profile_id = fields.Many2one(
        comodel_name='oacis.demo.profile',
        string='Demo Profile',
        help='Volumes/naming for the detected institution type. '
             'Leave empty to use coded defaults.',
    )
    reset_existing = fields.Boolean(
        string='Replace Existing Demo Data',
        default=True,
        help='Delete previously generated demo rows for this institution '
             'before generating. Real data is never touched.',
    )
    existing_demo_count = fields.Integer(
        string='Existing Demo Records',
        compute='_compute_existing_demo_count',
    )
    summary = fields.Text(string='Result', readonly=True)

    @api.depends('company_id')
    def _compute_institution_type(self):
        generator = self.env['oacis.demo.generator']
        for wizard in self:
            if wizard.company_id:
                wizard.institution_type = generator.resolve_institution_type(
                    wizard.company_id)
            else:
                wizard.institution_type = False

    @api.depends('company_id')
    def _compute_existing_demo_count(self):
        generator = self.env['oacis.demo.generator']
        for wizard in self:
            wizard.existing_demo_count = generator.existing_demo_count(
                wizard.company_id) if wizard.company_id else 0

    @api.onchange('company_id')
    def _onchange_company_id(self):
        for wizard in self:
            if not wizard.company_id:
                continue
            itype = self.env['oacis.demo.generator'].resolve_institution_type(
                wizard.company_id)
            lookup = 'university' if itype == 'legacy' else itype
            wizard.demo_profile_id = self.env['oacis.demo.profile'].search(
                [('institution_type', '=', lookup)], limit=1)

    def action_generate(self):
        self.ensure_one()
        generator = self.env['oacis.demo.generator']
        result = generator.generate(
            self.company_id,
            demo_profile=self.demo_profile_id or None,
            reset_first=self.reset_existing,
        )
        counts = result.get('counts', {})
        lines = ['Generated %s demo data for %s.' % (
            result.get('institution_type'), self.company_id.display_name)]
        lines += ['- %s: %s' % (key, val)
                  for key, val in sorted(counts.items())]
        self.summary = '\n'.join(lines)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_reset(self):
        self.ensure_one()
        if not self.existing_demo_count:
            raise UserError(_('No generated demo data found for %s.') % (
                self.company_id.display_name,))
        result = self.env['oacis.demo.generator'].reset_company_demo(
            self.company_id)
        self.summary = 'Removed %s demo records for %s. Real data untouched.' % (
            result.get('removed'), self.company_id.display_name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
