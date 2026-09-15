"""
Oacis Admission Applicant — Automation Extension (Phase A / Phase B)
Layers the automation engine over the existing ``oacis.admission.applicant``
lifecycle without touching the base file:

- ``write()``/``create()`` capture the previous ``state``/``stage_id`` and fire
  the automation engine after the ORIGINAL write logic has run (the base
  ``write()`` keeps syncing ``state`` <-> ``stage_id``; Python MRO guarantees
  our ``write()`` runs first and delegates via ``super()``).
- ``entrance_test_date`` stored field lets date-based automation rules search
  applicants by their (earliest) entrance test date.
- ``action_schedule_entrance`` (Phase B.2) auto-creates the entrance test line
  when a test exists for the applicant's cycle, so marks can be entered without
  a manual line add.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AdmissionApplicantAutomationExt(models.Model):
    _inherit = 'oacis.admission.applicant'

    entrance_test_line_ids = fields.One2many(
        comodel_name='oacis.admission.entrance.test.line',
        inverse_name='applicant_id', string='Entrance Test Lines',
    )

    entrance_test_date = fields.Date(
        string='Entrance Test Date',
        compute='_compute_entrance_test_date',
        store=True,
        help='Earliest entrance test date of this applicant. Computed from the '
             'entrance test line and used by date-based automation rules.',
    )

    @api.depends(
        'entrance_test_line_ids', 'entrance_test_line_ids.test_id',
        'entrance_test_line_ids.test_id.test_date',
    )
    def _compute_entrance_test_date(self):
        for record in self:
            dates = record.entrance_test_line_ids.mapped('test_id.test_date')
            record.entrance_test_date = min(dates) if dates else False

    def write(self, vals):
        old_states = {r.id: r.state for r in self}
        old_stages = {r.id: r.stage_id for r in self}
        res = super().write(vals)
        engine = self.env['oacis.admission.automation.engine']
        # Only fire for the axis that was explicitly written. The base write()
        # keeps ``state`` <-> ``stage_id`` in sync through its own nested
        # writes, so a stage-only kanban drag re-enters this method with a
        # state write; without this guard the transition would fire twice.
        if 'state' in vals:
            for record in self:
                if old_states.get(record.id) != record.state:
                    engine._fire_state_change(
                        record, old_states.get(record.id), record.state,
                    )
        if 'stage_id' in vals:
            for record in self:
                if old_stages.get(record.id) != record.stage_id:
                    engine._fire_stage_change(
                        record, old_stages.get(record.id), record.stage_id,
                    )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        engine = self.env['oacis.admission.automation.engine']
        for record in records:
            engine._fire_state_change(record, False, record.state)
        return records

    # ------------------------------------------------------------------
    # Phase B.2 — auto-create the entrance test line on scheduling
    # ------------------------------------------------------------------

    def action_schedule_entrance(self):
        res = super().action_schedule_entrance()
        TestLine = self.env['oacis.admission.entrance.test.line']
        for record in self:
            test = self.env['oacis.admission.entrance.test'].search([
                ('cycle_id', '=', record.cycle_id.id),
                ('company_id', '=', record.company_id.id),
                ('state', 'in', ('draft', 'scheduled')),
            ], limit=1)
            if not test:
                # No test configured for this cycle yet: marks entry is manual.
                continue
            existing_line = TestLine.search([
                ('test_id', '=', test.id),
                ('applicant_id', '=', record.id),
            ], limit=1)
            if not existing_line:
                TestLine.create({
                    'test_id': test.id,
                    'applicant_id': record.id,
                })
        return res
