# Phase 4 — Cohort-Driven Enrollment Defaults (Verification Audit)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Status:** COMPLETE (2026-08-05) — ZERO REGRESSION, 5 new tests green, migration verified on real DB.

---

## ROLE

You are a senior Odoo architect on UniCore. Phase 4 = leverage the Phase 3 `cohort_kind` so that
**student enrollment records the right cohort** for each program kind:

- Legacy `academic_year` — `batch_year` remains the cohort (100% unchanged).
- K-12 `grade_batch` — the student must carry a `grade_level_id` (a GRADE-type academic unit).
- Training / coaching `rolling` — the student must carry a `cohort_start_date`.

Hard exit criteria (from §5):
1. Legacy path 100% unchanged — `batch_year` still the cohort, **no new required fields** for
   university students, no student/enrollment behavior change for existing flows.
2. Zero regression on the full suite (identical pre-existing failure set).
3. Requirements enforced at both `create()` and `write()` time (grade_batch → grade level; rolling
   → start date), only for non-legacy programs.
4. No changes to program/cohort_kind semantics (Phase 3 untouched) and no admission/intake
   automation yet (deferred follow-on).

---

## WHAT CHANGED

### `unicore.student` model (`unicore/custom_addons/unicore_student/models/unicore_student.py`)
New fields in the ACADEMIC PLACEMENT section (after `batch_year`):
- `cohort_kind` — Selection **related** `program_id.cohort_kind`, `readonly`, **`store=True`**
  (a non-stored related field cannot be searched/grouped — this is why it is stored).
- `grade_level_id` — Many2one → `unicore.academic.unit`, domain
  `[('unit_type_id.code', '=', 'GRADE'), ('company_id', '=', company_id)]`, `tracking`,
  `ondelete='restrict'`.
- `cohort_start_date` — Date, `tracking`.
- `cohort_label` — computed (non-stored) display: `Batch {batch_year}` | grade `display_name` |
  `YYYY-MM-DD`, `depends('program_id.cohort_kind', 'batch_year', 'grade_level_id.display_name',
  'cohort_start_date')`.

New validation + wiring:
- `_check_student_cohort()` — raises `ValidationError` when the program's `cohort_kind` is
  `grade_batch` without `grade_level_id`, or `rolling` without `cohort_start_date`. For
  `academic_year` it imposes **nothing** (inert by design → zero regression).
- `create()` (existing override) now calls `records._check_student_cohort()` right after
  `super().create(vals_list)` (before partner auto-creation).
- NEW `write()` override calls `self._check_student_cohort()` only when `program_id`,
  `grade_level_id`, or `cohort_start_date` is in `vals`.
- Same constrains-skip rationale as Phases 1/3: a `@api.constrains` on those fields would not fire
  on anchor-less `create()` when the fields are absent from vals.

### Manifest (`unicore_student/__manifest__.py`)
- Added explicit `'unicore_academic_generic'` dependency (previously transitive via
  `unicore_academic`; no cycle — generic depends only on `unicore_base` + `unicore_security`).

### Views (`unicore_student/views/unicore_student_views.xml`)
- **Form** (Academic > Placement, second group): `cohort_kind` (readonly), `grade_level_id`
  (`invisible="cohort_kind != 'grade_batch'"`, `required="cohort_kind == 'grade_batch'"`,
  `no_create_edit`), `cohort_start_date` (`invisible`/`required` for `rolling`), `cohort_label`
  (readonly).
- **List**: `cohort_kind` + `cohort_label` as `optional="hide"` columns.
- **Search**: `<field name="cohort_kind"/>` + groupby filter `group_cohort_kind` ("Cohort Kind").
- No new models → no ACL changes.

---

## VERIFICATION (migration + zero regression)

### Migration path tested on an OLD-schema DB first
`-u unicore_student` on **`odoo_p0_baseline`** (pre-Phase-0 schema) and on the real **`odoo`** DB.

| Check | Result |
|---|---|
| `unicore_student.grade_level_id / cohort_start_date / cohort_kind` columns | ADDED ✓ (both DBs) |
| Upgrade exit code | EXIT=0 (both DBs) |
| Tracebacks during upgrade | ALL benign "External ID not found … Skipping deletion" cleanup; real DB: 162 tracebacks / 324 messages, **0 non-external errors** |
| Existing student rows | untouched (all new columns nullable, no backfill needed) |

### Zero regression — identical failure set
Full 18-module suite (with `/unicore_curriculum`) on the real `odoo` DB:

```
6 failed, 3 error(s) of 149 tests
```

The **9 failures are exactly the pre-existing set** (unchanged since Phase 0/1/2/3):
- `unicore_fees` — test_04, test_05, test_06, test_08 (ERROR), test_09
- `unicore_api` — test_14_current_semester
- `unicore_admission` — test_14_record_fee_payment (FAIL), test_12_publish_grade (ERROR)
- `unicore_website` — setUpClass error

Test count grew 144 → **149** (+5 Phase 4 tests). Isolated `/unicore_student` run: **0 failed,
0 errors of 16 tests** (11 existing + 5 new).

### Phase 4 tests
`unicore_student/tests/test_student_cohort.py` (5, tagged `unicore`/`unit`):
- test_01_legacy_student_unchanged — legacy student: `cohort_kind` academic_year, no grade/start
  required, `cohort_label` = "Batch 2025".
- test_02_grade_batch_requires_grade_level — create without grade → ValidationError; with grade → ok.
- test_03_rolling_requires_start_date — create without start date → ValidationError; with → ok.
- test_04_write_requires_grade_level — moving onto a grade_batch program without grade →
  ValidationError (program stays legacy after failed write), then works once grade set.
- test_05_label_follows_kind_on_switch — `cohort_label` follows kind when switching programs.

Test conventions: profile is company-level, so the school profile + grade unit + school program are
created **per test** (not in setUpClass) to avoid cross-test profile flips. Faculty code is
letters-only (`'PFAC'`); grade unit uses `unicore_academic_generic.unit_type_grade_level` ref.

---

## GOTCHAS ENCOUNTERED (Phase 4)

1. **A non-stored related field cannot be used in search or `group_by`** → `cohort_kind` is a stored
   related (`store=True`). This is the Odoo-19 searchable/groupable requirement re-hit from Phase 0.
2. **`create()`/`write()` override pattern again** (Phases 1/3 lesson): the cohort requirement check
   must be invoked explicitly, not via `@api.constrains`, or anchor-less creates skip it silently.
3. **Keep the check one-directional & legacy-inert**: only enforce *requirements* for non-legacy
   kinds; never reject extra data on legacy students (avoids breaking existing flows).
4. **Per-test profile setup**: `res.company.institution_profile_id` is company-level, so tests that
   need different profiles create their school profile/unit/program inside each test method.
5. The ~162 "External ID not found … Skipping deletion" tracebacks during upgrade are **pre-existing**
   benign cleanup, not from Phase 4.

---

## EXIT CRITERIA — ALL MET

- [x] Legacy path unchanged — no new required fields; `batch_year` remains the cohort; existing student tests still green.
- [x] Zero regression: identical `6 failed, 3 error(s)` pre-existing set; 144→149 tests.
- [x] Requirements enforced at create() AND write() for `grade_batch` (grade level) and `rolling` (start date).
- [x] Phase 3 `cohort_kind` semantics untouched; no admission/intake automation added.
- [x] Upgrade applied to real `odoo` DB (`-u unicore_student`), schema verified.

**Files touched:** `unicore/custom_addons/unicore_student/{models/unicore_student.py,
__manifest__.py, views/unicore_student_views.xml, tests/__init__.py,
tests/test_student_cohort.py (new)}`.
**DBs:** upgraded `odoo` (real) and `odoo_p0_baseline` (migration bed).

---

## NEXT PHASE (Phase 5 — planned, NOT started)
Phase 5 continues the multi-entity rollout. Candidate scope (to be confirmed against the deep
migration plan): **admission / intake automation** — auto-deriving grade level / cohort start date
at admission from the program's `cohort_kind`, plus portal/self-service displays of the student's
cohort. Apply the same discipline: verify → build → exit criteria → zero regression → record.
