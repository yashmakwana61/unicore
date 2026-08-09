"""Backfill the University (Legacy) profile onto companies.

Version 19.0.1.1.0 — activation of the institution-profile driver.

Before this version, ``res.company.institution_profile_id`` was never populated
(no migration, no wizard, no settings page), so every downstream consumer
(``is_legacy_institution``, cohort enforcement, grading dispatch, terminology
labels) took the legacy fallback forever and the config screens had no effect.

This migration attaches the seeded University (Legacy) profile to every company
that has none. UNI_LEGACY reproduces 100% of current behavior, so this is a pure
driver activation with zero observable change. Re-runnable (only fills empty).
"""

from odoo import SUPERUSER_ID, api


def _backfill_legacy_profile(cr, env):
    legacy = env.ref(
        'unicore_institution_profile.profile_university_legacy',
        raise_if_not_found=False,
    )
    if not legacy:
        return
    companies = env['res.company'].search(
        [('institution_profile_id', '=', False)])
    if companies:
        companies.write({'institution_profile_id': legacy.id})


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_legacy_profile(cr, env)
