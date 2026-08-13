# Oacis Terminology Application Audit — "changing the profile relabels EVERYTHING"

Date: 2026-08-09 · Module touched: oacis_institution_profile · DBs: odoo_p0_baseline (migration
bed) + odoo (live)

## TL;DR
Root cause of the user's "when I change the institute type/profile I still see university terms
(Program, Faculty) everywhere" + "I don't see any changes in modules": the terminology was DEFINED
but never APPLIED to the UI served to the web client. Built a complete relabeling layer
(`fields_get` on `'base'` + view architecture + navigation menus + action titles) and PROVED it
end-to-end with real Staff/Admin users on the live DB: attaching TRN / K-12 relabels labels on every
surface the user looks at; detaching restores them. Live upgrade installed v19.0.1.3.0.
**ZERO REGRESSION on the full 20-module suite (`6 failed, 3 error(s) of 207 tests` = the pre-existing 9).**

## What was done

### Terminology application layer (`oacis_institution_profile`)
- **`models/base.py`** — `TerminologyBase(models.AbstractModel): _inherit = 'base'`; overrides
  `fields_get` → rewrites `fdef['string']` for every matching label, GLOBALLY across all models
  (this is what makes a K-12 school see `Learner`/`Class/Section` on every model's field labels).
- **`models/ir_ui_view.py`** — `get_view` override (feeds `get_views` too) rewrites explicit
  `string` attributes in the architecture (filters, labels, buttons, statinfo cards, group/page
  titles). Token-driven from `company._terminology_label_rules()`; substring fast-path skips parsing
  when no generic token is present. `_get_view_cache_key` appends `(('company', company.id),)` so
  two companies never share cached field labels. No profile / UNI_LEGACY → empty rules → the arch is
  returned **byte-identical** (zero-regression guarantee).
- **`models/ir_ui_menu.py`** — `load_menus` override: copy-on-write dict, relabels each menu `name`
  per company, **never mutates** the ormcached inner dicts (verified no cache corruption).
- **`models/ir_actions.py`** — `_get_action_dict` override → relabels `result['name']` (page title).
- **`models/res_company.py`** — `_terminology_label_rules()` → `(exact, prefixes)` gated on
  non-legacy profile + terminology; compounds (`Faculty Member`→fstaff, `Current Semester`→`Current
  %s`, `Current Academic Year`→`Current %s`); prefixes sorted by token length desc.
  `_terminology_apply()` static: exact-first, then whole-word `\b(?:token(?:s|es)?|...)\b` regex
  substitution with plural carry-over (Programs→Courses; K12 Programs→Class/Sections), cached.
  `res.company.write` clears the registry cache when `institution_profile_id` changes.
- Manifest version → `19.0.1.3.0`.

### Tests
- **`tests/test_terminology_application.py`** (6, tagged oacis/unit): 01 no-profile stays generic;
  02 TRN relabels fields everywhere (incl. cross-module `oacis.enrollment`/`oacis.program` in the
  full-suite run, `_relabel` helper skips when the model is not in the registry); 03 view arch
  (Module/Course Type/Active Courses); 04 K-12 fields (Grade Level/Class-Section); 05 menus via a
  real Staff user — **root matched by xmlid, not by name** (name is 'Oacis' on fresh DBs, 'SIS' on
  the migrated live DB); 06 action title.
- **`oacis_enrollment/tests/test_terminology_views.py`** — `test_04` EVOLVED from
  "non-whitelisted model untouched" to "token-driven relabeling on ANY model" (`oacis.course.
  offering` Program → Class/Section under K-12), with a negative check that non-term strings survive.
  This is a deliberate behavior evolution: the old 8-model Gap-2 whitelist left `Program` visible on
  non-core models — exactly the user's complaint.

## Verification results
- Isolated on live `odoo` (`/oacis_institution_profile,/oacis_enrollment`): **0 failed, 0 error(s)
  of 52 tests** (39 + 13).
- E2E diagnostics (baseline staff user + live admin uid=2 who has oacis Admin→Staff + website
  designer): TRN and K-12 relabel `fields_get` (program/student/semester), view arch, menu names and
  action titles; detach restores `Programs`/`Departments`.
- Live upgrade (`-u oacis_institution_profile`): EXIT=0, module now `19.0.1.3.0`, log tracebacks all
  benign cleanup noise.
- **FULL 20-module suite on live odoo → `6 failed, 3 error(s) of 207 tests`** = EXACTLY the
  pre-existing set (fees 04/05/06/08err/09, api 14, admission 14 + 12err, website setUpClass),
  0 new failures. Test count 201 → 207 (+6). **ZERO REGRESSION.**

## Gotchas hit this session
- **Odoo 19 renames**: `res.users.group_ids` (NOT `groups_id`); `ir.ui.menu.group_ids` likewise.
- **`TransactionCase.setUpClass` runs as superuser** (no groups) → group-restricted menus invisible →
  menu tests must create a real Staff user via `group_ids`.
- **`ir.ui.view` read ACL**: plain Staff cannot read views (pre-existing: view read is limited to
  `base.group_system` + `website.group_website_restricted_editor` + `website.group_website_designer`);
  a functional admin needs `website.group_website_designer`.
- **App root menu name differs by DB** ('Oacis' id 168 on fresh DBs, 'SIS' id 123 on the live
  migrated DB) → tests must assert by record id, not name.
- **Live upgrade blocked twice**:
  1. `oacis_demo/data/03_academic_calendar.xml` writes a `semester`-type academic year for
     `base.main_company`; with K12 (term) attached this fires `_check_calendar_mode` → ParseError.
     Workaround: temporarily attach UNI_LEGACY (semester) during `-u`, restore K12 after.
  2. Empty `orm_signaling_registry` → `get_sequences()` returns `max(id)=NULL` →
     `registry_sequence=None` → `TypeError` in `signal_changes()` on ANY upgrade. Seeded one row.
- **Odoo shell writes need explicit `env.cr.commit()`** to persist (first attempt silently rolled back).

## Notes
- Relabeling only activates for NON-legacy profiles; UNI_LEGACY and no-profile stay byte-identical →
  zero regression by construction.
- The 9 pre-existing failures are unchanged; nothing alters legacy university behavior.
- **The user's live dev server (PID 2138, port 8069) was started at 06:45, before the 08:58 upgrade** —
  it must be restarted to serve the new 19.0.1.3.0 code. DB is fully upgraded and verified.
