"""Install hooks for oacis_institution_profile.

19.0.1.1.0 — driver activation: attach the seeded University (Legacy) profile
to every company so the institution-profile config actually drives behavior.
"""


def _backfill_legacy_profile(env):
    """Attach the University (Legacy) profile to companies without one.

    Re-runnable and multi-company safe. The legacy profile reproduces 100% of
    current behavior, so attaching it activates the profile driver (terminology
    relabeling, grading dispatch, feature toggles) with zero observable change.
    """
    legacy = env.ref(
        'oacis_institution_profile.profile_university_legacy',
        raise_if_not_found=False,
    )
    if not legacy:
        return
    companies = env['res.company'].search(
        [('institution_profile_id', '=', False)])
    if companies:
        companies.write({'institution_profile_id': legacy.id})


def post_init_hook(env):
    """Attach the legacy profile on fresh installs (driver activation)."""
    _backfill_legacy_profile(env)
