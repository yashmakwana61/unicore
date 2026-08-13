"""
Oacis Student Extension — Scholarship Module
Adds scholarship summary to student record.
"""

import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class OacisStudentScholarshipExt(models.Model):
    _inherit = 'oacis.student'

    scholarship_application_ids = fields.One2many(
        comodel_name='oacis.scholarship.application',
        inverse_name='student_id',
        string='Scholarship Applications',
        readonly=True,
    )
    scholarship_count = fields.Integer(
        string='Scholarships',
        compute='_compute_scholarship_summary',
        store=False,
    )
    active_scholarship_count = fields.Integer(
        string='Active Awards',
        compute='_compute_scholarship_summary',
        store=False,
    )
    total_scholarship_received = fields.Monetary(
        string='Total Scholarship Received',
        compute='_compute_scholarship_summary',
        store=False,
        currency_field='scholarship_currency_id',
    )
    scholarship_currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
    )

    def _compute_scholarship_summary(self):
        Award = self.env['oacis.scholarship.award']
        for rec in self:
            apps = rec.scholarship_application_ids
            rec.scholarship_count = len(apps)
            approved = apps.filtered(
                lambda a: a.application_state
                == 'approved',
            )
            rec.active_scholarship_count = len(approved)
            awards = Award.search([
                ('student_id', '=', rec.id),
                ('award_state', '=', 'disbursed'),
            ])
            rec.total_scholarship_received = sum(
                a.award_amount for a in awards
            )

    def action_view_scholarship_applications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Scholarship Applications'),
            'res_model': 'oacis.scholarship.application',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {
                'default_student_id': self.id,
            },
        }
