# UniCore Config Activation Audit (post-migration "config does nothing" fix)

Date: 2026-08-07 · Modules touched: unicore_institution_profile, unicore_academic_generic,
unicore_calendar · DBs: odoo_p0_baseline (migration bed) + odoo (live)

## TL;DR
Root cause of "institution profile / terminology / grading scheme / academic units / unit types
config screens work but have no effect": `res.company.institution_profile_id` was NEVER set (no
backfill, no wizard, no settings), so every consumer fell back to legacy forever; 3 of the profile's
6 config dimensions (`academic_unit_level_ids`, `calendar_mode`, `feature_toggle_ids`) were consumed
nowhere in production code.

Fix (user-approved): (A) backfill UNI_LEGACY onto companies so the driver is live — zero behavior
change (UNI_LEGACY == no-profile in every consumer); (B) wire the three dead fields to actually
enforce/drive behavior. **ZERO REGRESSION on the full 20-module suite.**

## What was done

### Phase 1 — Activate the driver (backfill)
- `__manifest__.py` version → `19.0.1.1.0`; `post_init_hook: post_init_hook`.
- NEW `hooks.py` `_backfill_legacy_profile(env)`: `env.ref('unicore_institution_profile
  .profile_university_legacy', raise_if_not_found=False)` → `env['res.company'].search(
  [('institution_profile_id','=',False)]).write({'institution_profile_id': legacy.id})`.
  Re-runnable (only fills empty).
- NEW `migrations/19.0.1.1.0/post-migrate.py` `migrate(cr, version)`: same helper (upgrade path).
- `tests/test_institution_profile.py` test_05 updated: default is now UNI_LEGACY (was NULL); detach/
  reattach still works. Documented, deliberate behavior change.

### Phase 2 — Wire `academic_unit_level_ids` (enforce allowed unit types)
- Enforcement MOVED into `unicore_institution_profile/models/unicore_academic_unit.py`
  (`_inherit='unicore.academic.unit'` + `@api.constrains('company_id','unit_type_id')
  _check_unit_type_allowed`): strict only when profile present AND allow-list non-empty. UNI_LEGACY
  lists all 8 types → never fires. Empty list / no profile → unrestricted.
- **ARCHITECTURE GOTCHA**: cannot live in unicore_academic_generic — that module loads BEFORE
  institution_profile (which depends on it), so `res.company.institution_profile_id` doesn't exist
  there → AttributeError. `@api.constrains` on an `_inherit` model IS registered (constraint methods
  collected via `getmembers(cls, is_constraint)` walking the MRO).
- Tests: `unicore_institution_profile/tests/test_academic_unit_levels.py` (4) — school rejects
  Faculty / accepts Grade, no-profile+empty unrestricted, UNI_LEGACY accepts all.

### Phase 3 — Wire `calendar_mode` (gate academic-year structure)
- `unicore_calendar/models/unicore_academic_year.py`: create() defaults `year_type='term'` when
  company profile.calendar_mode=='term' and year_type absent; create+write call `_check_term_structure()`
  AND new `_check_calendar_mode()` (one-directional: term profile ⇒ term years; semester/other = flexible).
- Tests: `unicore_calendar/tests/test_calendar_mode_wiring.py` (3).

### Phase 4 — Wire `feature_toggle_ids` (per-company menu gating)
- `res_company.py`: NEW `has_feature(code)`, `_enabled_feature_codes()` (no profile → all seeded
  feature codes), computed `enabled_feature_codes` Char, and `write()` override that clears the
  registry cache when `institution_profile_id` changes (base `load_menus` is NOT company-keyed).
- NEW `ir_ui_menu.py` (`_inherit='ir.ui.menu'`): override `_filter_visible_menus()` — maps menu
  module → feature code via `_FEATURE_MODULES` (13 modules); hides menus whose feature is disabled;
  UNI_LEGACY (all features) hides nothing.
- View: read-only `enabled_feature_codes` on company form.
- Tests: `test_feature_gating.py` (3). GOTCHA: `ir.ui.menu.action` is a **Reference** field → set as
  `'ir.actions.act_window,%d' % action.id`, NOT `action.id`.

## Verification results
- Isolated (odoo_p0_baseline): `/unicore_institution_profile,/unicore_academic_generic,
  /unicore_calendar` → **0 failed, 0 errors** (authoritative result line; per-module stats 10+11+38).
  First run had 9 errors (3 real bugs, fixed): (1) constrains in wrong module (circular dep),
  (2) Phase 2 test in wrong module (profile model not loaded), (3) Reference field format.
- Downstream (odoo_p0_baseline): `/unicore_curriculum,/unicore_student,/unicore_enrollment,
  /unicore_grading,/unicore_admission,/unicore_academic` → **1 failed, 1 error** = ONLY the
  pre-existing admission pair (test_12 ERROR + test_14 FAIL). All others pass.
- Migration path: `-u unicore_institution_profile,unicore_academic_generic,unicore_calendar` on
  odoo_p0_baseline THEN live odoo → EXIT=0. psql confirms on BOTH DBs:
  `res_company.institution_profile_id` = UNI_LEGACY attached to PreciseFect University.
- **FULL 20-module suite on live odoo → `6 failed, 3 error(s) of 196 tests`** = EXACTLY the
  pre-existing set (fees 04/05/06/08err/09, api 14, admission 14 + 12err, website setUpClass),
  0 new failures. Test count 186 → 196 (+10: 4 unit-levels + 3 calendar-mode + 3 feature-gating).
  **ZERO REGRESSION.**

## Notes / gotchas
- Per-module `tests.stats` "N tests" sums HIGHER than the `of N tests` result line (e.g. isolated
  59 vs 43; full 264 vs 196). This is Odoo's `log_stats` counting unique stopped-test IDs across
  merged at_install+post_install reports vs `testsRun`. Pre-existing reporting quirk — use the
  result line as authoritative (matches the 186→196 trajectory exactly).
- Cleanup-XML `<delete>` of already-missing action IDs (unicore_academic / unicore_calendar cleanup
  files) produce "External ID not found" tracebacks — benign noise.
- `@api.constrains` referencing profile fields must live in the profile module (circular-dep rule):
  a module can NEVER reference a field/model defined in a module that DEPENDS on it.
- The 9 pre-existing failures are unchanged; the test_05 default (UNI_LEGACY) change is the only
  deliberate behavior delta and it is regression-safe (legacy consumers behave identically).
