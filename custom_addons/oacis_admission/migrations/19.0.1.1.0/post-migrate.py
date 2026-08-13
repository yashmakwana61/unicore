"""Phase 2: backfill configurable admission stages for existing data.

Runs after the module update on databases that already contain applicants
created before the ``stage_id`` field existed:

1. Ensures every company that owns applicants has its default 13-stage
   pipeline (idempotent -- custom pipelines are left untouched).
2. Backfills ``stage_id`` on existing applicants from their ``state`` so the
   kanban (now grouped by ``stage_id``) shows them in the right column.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Stage = env['oacis.admission.stage']
    Applicant = env['oacis.admission.applicant']

    applicants = Applicant.search([])
    company_ids = applicants.company_id.ids
    for company in env['res.company'].browse(set(company_ids)):
        Stage._ensure_default_stages(company)

    for applicant in applicants.filtered(lambda a: not a.stage_id):
        stage = Stage._get_stage_for_state(
            applicant.company_id.id, applicant.state)
        if stage:
            applicant.stage_id = stage
