# Oacis Institution Profile Templates Audit (Phase 5)

Date: 2026-08-07 · Module touched: oacis_institution_profile · DBs: odoo_p0_baseline (migration
bed) + odoo (live)

## TL;DR
Delivered the complete ready-to-attach Institution Profile catalog — one profile per supported
`institution_type` — each carrying its FULL related settings (calendar_mode, grading scheme,
academic unit levels, terminology, feature toggles). Seeded as `noupdate=1` so admins can
customize freely; upgrades only add missing records. **ZERO REGRESSION on the full 20-module suite.**

## What was done

### Seed catalog (NEW `data/oacis_institution_profile_templates.xml`, noupdate=1)
Four new terminology profiles + four new institution profiles (UNI_LEGACY + K12_SCHOOL already
shipped in `oacis_institution_profile_data.xml`). All new profiles: `is_legacy_university=False`.

| XML ID | Code | type | calendar | grading scheme_id | unit levels | terminology (labels) | features |
|---|---|---|---|---|---|---|---|
| profile_college | COL | college | semester | CREDIT_GPA | FAC, DEP, STREAM | COL: Faculty, Department, Degree Program, Student, Faculty/Staff, Semester, Academic Year | all 13 |
| profile_training_institute | TRN | training | rolling_batch | SIMPLE_PCT | BATCH, OTHER | TRN: faculty hidden, Module, Course, Trainee, Trainer, Cycle, Year | 9 (no ALUMNI/CONVOCATION/HOSTEL/THESIS) |
| profile_academy | ACA | academy | term | PASS_FAIL | GRADE, BATCH, OTHER | ACA: faculty hidden, Subject, Batch, Student, Instructor, Term, Session | 8 (TRN minus TRANSPORT) |
| profile_coaching_center | COA | coaching | rolling_batch | CERT_ONLY | BATCH, OTHER | COA: faculty hidden, Subject, Batch, Student, Coach, Cycle, Year | 7 (ACA minus SCHOLARSHIP) |

References same-module `feature_*` / `grading_scheme_*` (loaded earlier in
`oacis_institution_profile_data.xml`) and `oacis_academic_generic.unit_type_*`.
- `__manifest__.py` version → `19.0.1.2.0`; data list now also includes
  `data/oacis_institution_profile_templates.xml` (after the base data file, before views/menus).

### Tests (NEW `tests/test_profile_templates.py`, tagged `('oacis','unit')`, 5 tests)
- `test_01_college_profile_wiring` / `test_02_training_profile_wiring` / `test_03_academy_profile_wiring`
  / `test_04_coaching_profile_wiring`: assert code, type, calendar_mode, effective_grading_scheme,
  unit-type codes (sorted), feature toggles, and terminology labels.
- `test_05_company_attachment_effect`: attach TRN → `get_term_label('student')=='Trainee'`,
  `has_feature(FEES/ADMISSION)` True, `has_feature(HOSTEL/CONVOCATION)` False; detach → all features,
  label None. Helpers `_profile(xmlid)` via `env.ref`, `_unit_codes(profile)`.

### Gotcha hit during verification
- **XML comments cannot contain `--`** (XML spec). The ASCII-art separator comments built from `-`
  runs (`<!-- -----... -->`) blew up with `XMLSyntaxError: Double hyphen within comment` at load
  (EXIT=255). Fixed by using `=` runs for all comment separators. First `=`, others were `-`.
- M2M rel tables are `oacis_institution_profile_unit_type_rel` (cols `profile_id`,`unit_type_id`)
  and `oacis_institution_profile_feature_rel` (cols `profile_id`,`feature_id`); feature model is
  `oacis_institution_feature`.

## Verification results
- Isolated (odoo_p0_baseline): `/oacis_institution_profile` with `-u oacis_institution_profile`
  → **0 failed, 0 error(s) of 33 tests** (single-module result line; includes the 5 new tests).
  First run EXIT=255 due to the XML comment bug above; fixed, re-run clean.
- psql (odoo_p0_baseline): all 6 profiles present (UNI_LEGACY/K12_SCHOOL/COL/TRN/ACA/COA) with
  correct type + calendar_mode + grading_scheme_id + terminology; terminology table has all 6 with
  correct labels (faculty blank on TRN/ACA/COA/K12 = hidden concept). M2M wiring verified:
  COL=DEP,FAC,STREAM + 13 features; TRN=BATCH,OTHER + 9; ACA=BATCH,GRADE,OTHER + 8; COA=BATCH,OTHER + 7.
- Live upgrade (odoo): `-u oacis_institution_profile` → EXIT=0; all 6 profiles present. Log
  tracebacks are the known benign "Skipping deletion for missing XML ID" noise from cleanup files.
- **FULL 20-module suite on live odoo → `6 failed, 3 error(s) of 201 tests`** = EXACTLY the
  pre-existing set (fees 04/05/06/08err/09, api 14, admission 14 + 12err, website setUpClass),
  0 new failures. Test count 196 → 201 (+5 new). **ZERO REGRESSION.**

## Notes
- All template profiles are `noupdate` seeds — admins can override any field; an upgrade only adds
  records that are missing (won't clobber customizations). Document this for end users.
- Feature spread intentionally ranges 13 → 9 → 8 → 7 to show progressive gating (university > training
  > academy > coaching). UNI_LEGACY remains the "everything on" default (backfilled onto companies).
- The 9 pre-existing failures are unchanged; nothing in this phase alters runtime consumer behavior
  until an admin actually attaches one of the new profiles to a company.
