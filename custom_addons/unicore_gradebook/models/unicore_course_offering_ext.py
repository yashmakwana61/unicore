"""
UniCore Course Offering Extension — Grade Book
==============================================

Adds the reverse grade book link and a smart button to the course
offering form so faculty can jump straight into the grade book of
an offering. Additive view/model extension only.
"""

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class UniCoreCourseOfferingGradeBookExt(models.Model):
    _inherit = 'unicore.course.offering'

    gradebook_config_ids = fields.One2many(
        comodel_name='unicore.gradebook.config',
        inverse_name='course_offering_id',
        string='Grade Books',
    )
    gradebook_config_count = fields.Integer(
        string='Grade Books',
        compute='_compute_gradebook_config_count',
    )

    @api.depends('gradebook_config_ids')
    def _compute_gradebook_config_count(self):
        for rec in self:
            rec.gradebook_config_count = len(
                rec.gradebook_config_ids
            )

    def action_open_gradebook(self):
        """Open the grade book of this offering, or a fresh form."""
        self.ensure_one()
        config = self.gradebook_config_ids[:1]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grade Book'),
            'res_model': 'unicore.gradebook.config',
            'view_mode': 'form',
            'res_id': config.id if config else False,
            'context': {
                'default_course_offering_id': self.id,
            },
        }
