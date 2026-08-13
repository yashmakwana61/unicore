"""
UniCore Student Extension — Guardian Module
Extends unicore.student to add guardian relationship
fields and the action to open guardian records.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class UniCoreStudentGuardianExt(models.Model):
    _inherit = 'unicore.student'

    guardian_rel_ids = fields.One2many(
        'unicore.guardian.student.rel',
        'student_id',
        string='Guardian Relationships',
    )
    guardian_count = fields.Integer(
        string='Guardians',
        compute='_compute_guardian_count',
        store=False,
    )
    primary_guardian_id = fields.Many2one(
        'unicore.guardian',
        string='Primary Guardian',
        compute='_compute_primary_guardian',
        store=False,
    )
    financial_guarantor_id = fields.Many2one(
        'unicore.guardian',
        string='Financial Guarantor',
        compute='_compute_financial_guarantor',
        store=False,
    )

    @api.depends('guardian_rel_ids')
    def _compute_guardian_count(self):
        for rec in self:
            rec.guardian_count = len(rec.guardian_rel_ids)

    @api.depends('guardian_rel_ids',
                 'guardian_rel_ids.is_primary_guardian',
                 'guardian_rel_ids.is_active_relationship')
    def _compute_primary_guardian(self):
        for rec in self:
            primary_rel = rec.guardian_rel_ids.filtered(
                lambda r: r.is_primary_guardian
                          and r.is_active_relationship,
            )
            rec.primary_guardian_id = (
                primary_rel[0].guardian_id
                if primary_rel else False
            )

    @api.depends('guardian_rel_ids',
                 'guardian_rel_ids.is_financial_guarantor',
                 'guardian_rel_ids.is_active_relationship')
    def _compute_financial_guarantor(self):
        for rec in self:
            guarantor_rel = rec.guardian_rel_ids.filtered(
                lambda r: r.is_financial_guarantor
                          and r.is_active_relationship,
            )
            rec.financial_guarantor_id = (
                guarantor_rel[0].guardian_id
                if guarantor_rel else False
            )

    def action_open_guardians(self):
        """Open the list of guardian profiles
        linked to this student."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Guardians'),
            'res_model': 'unicore.guardian',
            'view_mode': 'list,form',
            'domain': [
                ('student_rel_ids.student_id', '=', self.id),
            ],
            'context': {
                'default_company_id': self.company_id.id,
            },
        }
