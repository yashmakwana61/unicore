# Phase 5 — Admission / Intake Cohort Automation (Verification Audit)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Status:** COMPLETE (2026-08-05) — ZERO REGRESSION, 3 new tests green, migration verified on real DB.

---

## ROLE

You are a senior Odoo architect on UniCore. Phase 5 = automate the cohort for **rolling-intake**
(training / coaching) programs so the existing **admission flow needs zero changes**, while keeping
the legacy university path and the K-12 grade-batch path exactly as they are.

The admission module creates students without any cohort fields
(`unicore_admission/models/admission_applicant.py` → `action_confirm_admission()` →
`Student.sudo().create(student_vals)`). Phase 4 made `cohort_start_date` *required* for rolling
programs — meaning an admission-created rolling student would fail validation. Phase 5 removes that
friction at the source by **auto-filling** the cohort start date from the admission date, at the
student level, so every upstream caller (admission, portal, API, manual) benefits automatically.

Hard exit criteria:
1. Legacy path 100% unchanged — `academic_year` students untouched (still `batch_year` only).
2. `grade_batch` stays **explicit** — grade selection is user-owned and never auto-derived.
3. Rolling `cohort_start_date` is auto-filled from `admission_date` when absent; an **explicitly
   provided value is never overwritten**.
4. Zero regression on the full suite (identical pre-existing failure set: `6 failed, 3 error(s)`).

---

## WHAT CHANGED

### `unicore.student` model (`unicore/custom_addons/unicore_student/models/unicore_student.py`)
- **`create()` intake automation** — inside the existing `@api.model_create_multi` vals loop (after
  the `student_id_number` sequence assignment):
  ```python
  if not vals.get('cohort_start_date'):
      program = self.env['unicore.program'].browse(vals.get('program_id'))
      if (program.cohort_kind == 'rolling' and vals.get('admission_date')):
          vals['cohort_start_date'] = vals['admission_date']
  ```
  Defaults are injected **before** `super().create()` (no re-entrant write during create). Missing
  `program_id` → `browse(False)` → empty recordset → `cohort_kind` is `False` → skipped. Legacy and
  grade_batch kinds are untouched. An explicit `cohort_start_date` in vals is never replaced.
- **`action_enroll()` safety net** — before the state transition, a rolling student with no
  `cohort_start_date` gets it filled from `admission_date` (covers students created before Phase 5
  or via any path that bypassed the create default).
- **NEW `@api.onchange('program_id', 'admission_date')` → `_onchange_cohort_defaults()`** — suggests
  `cohort_start_date = admission_date` for rolling programs when the field is empty (UX only; value
  persists only on save).

No new fields, no new models, no ACL changes. `grade_batch` semantics (Phase 4) are untouched.

### Display — legacy output byte-identical (both guarded by `student.cohort_kind != 'academic_year'`)
- **Student ID card** (`unicore_student/views/unicore_student_id_card_template.xml`): new `COHORT:`
  line after the `BATCH:` line using `student.cohort_label`, shown only for non-legacy kinds.
- **Portal student dashboard** (`unicore_portal_student/views/portal_student_templates.xml`, welcome
  header ~line 142): `| Cohort: <cohort_label>` appended after Year, only for non-legacy kinds.

---

## VERIFICATION (migration + zero regression)

### Migration path tested on an OLD-schema DB first
`-u unicore_student,unicore_portal_student` on **`odoo_p0_baseline`** (pre-Phase-0 schema) and on
the real **`odoo`** DB.

| Check | Result |
|---|---|
| Upgrade exit code | EXIT=0 (both DBs) |
| Tracebacks during upgrade | ALL benign "External ID not found … Skipping deletion" cleanup / docutils "Unexpected indentation" warnings; **0 real errors** |
| Schema | No new columns (cohort fields already exist from Phase 4); templates reloaded cleanly |

### Zero regression — identical failure set
Full 18-module suite (with `/unicore_curriculum`) on the real `odoo` DB:

```
6 failed, 3 error(s) of 152 tests
```

The **9 failures are exactly the pre-existing set** (unchanged since Phase 0/1/2/3/4):
- `unicore_fees` — test_04, test_05, test_06, test_08 (ERROR), test_09
- `unicore_api` — test_14_current_semester
- `unicore_admission` — test_14_record_fee_payment (FAIL), test_12_publish_grade (ERROR)
- `unicore_website` — setUpClass error

Test count grew 149 → **152** (+3 Phase 5 tests). Isolated `/unicore_student` run: **0 failed,
0 errors of 19 tests** (16 existing + 3 new). Isolated `/unicore_portal_student` run: 0 tests, clean.

### Phase 5 tests
`unicore_student/tests/test_student_cohort.py` (now 8, tagged `unicore`/`unit`):
- **test_03 EVOLVED** — `test_03_rolling_requires_start_date` → `test_03_rolling_intake_auto_fills_start`:
  a rolling student created without an explicit start date now **auto-fills** `cohort_start_date` from
  `admission_date` (was: `ValidationError`). This is a deliberate, documented behavior evolution of a
  Phase 4 test (NOT part of the 9 pre-existing failures).
- test_06_rolling_explicit_start_respected — an explicit start date is never overwritten.
- test_07_grade_batch_still_requires_grade — Phase 5 does **not** auto-derive grades; missing grade
  still raises `ValidationError`.
- test_08_enroll_works_for_auto_filled_rolling — an auto-filled rolling student enrolls cleanly
  (`action_enroll()` → `student_state == 'enrolled'`) and keeps the correct `cohort_label`.

---

## GOTCHAS ENCOUNTERED (Phase 5)

1. **Phase 4 `test_03` intentionally broke** — create() now auto-fills the rolling start date, so the
   old "rolling without start raises" assertion no longer holds. This is the correct evolution: the
   requirement is now auto-satisfied at the source (admission flow needs no change). Updated + documented.
2. **Auto-fill must be injection-only**: set the default into `vals` **before** `super().create()` to
   avoid a re-entrant `write()` during `create()` (which would otherwise trip the Phase 4 write check
   and duplicate work). Never overwrite an explicitly supplied value.
3. **`browse(vals.get('program_id'))` is safe on empty/absent values** — returns an empty recordset,
   `cohort_kind` is `False`, the fill is skipped. No special-casing needed.
4. **Keep display additive & conditional** — ID card and portal only show COHORT when
   `cohort_kind != 'academic_year'`, so legacy documents/renderings are byte-identical (same
   discipline as every prior phase).
5. The ~162 "External ID not found … Skipping deletion" tracebacks during upgrade remain **pre-existing
   benign** cleanup, not from Phase 5.

---

## EXIT CRITERIA — ALL MET

- [x] Legacy path unchanged — `academic_year` students untouched; existing tests still green.
- [x] `grade_batch` stays explicit — no auto-derivation (test_07).
- [x] Rolling intake auto-fills `cohort_start_date` from `admission_date` on create + enroll safety net;
      explicit values never overwritten (test_03, test_06, test_08).
- [x] Admission module untouched — automation lives at the student level where every caller benefits.
- [x] Zero regression: identical `6 failed, 3 error(s)` pre-existing set; 149→152 tests.
- [x] Upgrade applied to real `odoo` DB (`-u unicore_student,unicore_portal_student`), schema verified.

**Files touched:** `unicore/custom_addons/unicore_student/{models/unicore_student.py,
views/unicore_student_id_card_template.xml, tests/test_student_cohort.py}`;
`unicore/custom_addons/unicore_portal_student/views/portal_student_templates.xml`.
**DBs:** upgraded `odoo` (real) and `odoo_p0_baseline` (migration bed).

---

## NEXT PHASE (candidates, not yet scoped)
- Admission cycle → `cohort_kind` binding / intake windows per cohort kind.
- Enrollment / course-offering cohort rollup (schedule & grading filtered by cohort).
- Graduation / convocation cohort grouping (certificates by cohort label).
- Report & portal cohort filters (student list, fees, attendance grouped by cohort).
- K-12 academic calendar (terms / grades) and terminology (class / grade / division labels).
