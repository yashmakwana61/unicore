# Phase 7 — Enrollment Cohort Rollup (Verification Audit)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Status:** COMPLETE (2026-08-05) — ZERO REGRESSION, 4 new tests green, migration verified on real DB.

---

## ROLE

You are a senior Odoo architect on UniCore. Phase 7 = roll the student's cohort context up onto
`unicore.enrollment` (course enrollment) so enrollments can be **searched and grouped by cohort**:

- K-12 `grade_batch` — slice enrollments by **grade level** (e.g. all Grade 5 enrollments).
- Training / coaching `rolling` — slice enrollments by **intake** (cohort start date).
- Legacy `academic_year` — slice enrollments by **batch year** (the existing university grouping).

Everything is purely **additive** and **legacy-inert**: no new required fields, no behavior change to
create/write/enroll, no new table. For legacy universities an enrollment simply carries
`batch_year` + a `'Batch YYYY'` label and behaves exactly as before.

Hard exit criteria:
1. Legacy path 100% unchanged — legacy enrollments are untouched and carry only batch_year/label.
2. Cohort rollup fields are **stored relateds** (searchable + groupable).
3. Zero regression on the full suite (identical pre-existing failure set: `6 failed, 3 error(s)`).
4. No behavior change to create/write/enroll flows — rollup is read-only derived data.

---

## WHAT CHANGED

### `unicore.enrollment` model (`unicore/custom_addons/unicore_enrollment/models/unicore_enrollment.py`)
- **Stored related cohort fields** (after the `campus_id` block, before `display_name`) — all
  `readonly=True, store=True` so enrollments are searchable/groupable by cohort (the Phase 4/6 lesson:
  non-stored related/computed fields cannot be searched or grouped):
  - `cohort_kind` — Selection, related `student_id.cohort_kind`.
  - `grade_level_id` — Many2one → `unicore.academic.unit`, related `student_id.grade_level_id`.
  - `cohort_start_date` — Date, related `student_id.cohort_start_date`.
  - `batch_year` — Integer, related `student_id.batch_year`.
- **`cohort_label`** — new computed (non-stored) Char, `depends('student_id.cohort_label')`,
  = the student's `cohort_label` (`Batch YYYY` | grade display_name | `YYYY-MM-DD`). Display-only.

No new models, no ACL changes. Migration adds 4 stored columns to the existing table (no new table).
The manifest already depends on `unicore_student` (line 21) — no dependency change needed;
`unicore.academic.unit` is available transitively.

### Views (`unicore_enrollment/views/unicore_enrollment_views.xml`)
- **Form**: new `<group name="cohort" string="Cohort">` after the `enrollment_details` group (before
  `academic_result`). Left: `cohort_kind` + `cohort_label` (readonly). Right (kind-specific, readonly):
  `grade_level_id` `invisible="cohort_kind != 'grade_batch'"`, `cohort_start_date`
  `invisible="cohort_kind != 'rolling'"`, `batch_year` `invisible="cohort_kind != 'academic_year'"`.
- **List**: added `cohort_kind` + `cohort_label` (`optional="hide"`) after `campus_id`.
- **Search**: added `<field name="cohort_kind"/>` after `course_offering_id`, and 4 new groupbys on the
  group-by group after `group_by_grade`: `group_by_cohort` ("Cohort Kind"), `group_by_grade_level`
  ("Grade Level"), `group_by_intake` ("Intake Date"), `group_by_batch` ("Batch Year").

---

## VERIFICATION (migration + zero regression)

### Migration path tested on an OLD-schema DB first
`-u unicore_enrollment` on **`odoo_p0_baseline`** (pre-Phase-0 schema) and on the real **`odoo`** DB.

| Check | Result |
|---|---|
| Upgrade exit code | EXIT=0 (both DBs) |
| ERROR/CRITICAL lines | 3 (baseline) / 0 CRITICAL (real) — all pre-existing docutils "Unexpected indentation" docstring warnings, 0 real errors |
| Schema | 4 stored columns added on `unicore.enrollment` (`cohort_kind`, `grade_level_id`, `cohort_start_date`, `batch_year`); no new table |

### Zero regression — identical failure set
Full 18-module suite (with `/unicore_curriculum`) on the real `odoo` DB:

```
6 failed, 3 error(s) of 160 tests
```

The **9 failures are exactly the pre-existing set** (unchanged since Phase 0/1/2/3/4/5/6):
- `unicore_fees` — test_04, test_05, test_06, test_08 (ERROR), test_09
- `unicore_api` — test_14_current_semester
- `unicore_admission` — test_14_record_fee_payment (FAIL), test_12_publish_grade (ERROR)
- `unicore_website` — setUpClass error

Test count grew 156 → **160** (+4 Phase 7 tests). Isolated `/unicore_enrollment` run: **0 failed,
0 errors of 9 tests** (5 existing + 4 new).

### Phase 7 tests
`unicore_enrollment/tests/test_enrollment_cohort.py` (NEW, 4, tagged `unicore`/`unit`); setUpClass
mirrors `test_enrollment_model.py` (company profile False, faculty `PFSCI`, dept `P7MATH`, program
`P7BSCMATH`, campus `P7CAMPUS`, AY `P7AY2627`, semester `P7EVEN`, course `P7LA301`, open offering
max 60, grade-type ref):
- test_01_legacy_enrollment_cohort — legacy enrollment carries `batch_year == 2025`,
  `cohort_kind == 'academic_year'`, no grade/start, `cohort_label == 'Batch 2025'`.
- test_02_grade_enrollment_cohort — school `grade_batch` enrollment carries the student's
  `grade_level_id` and label = the grade unit's display_name.
- test_03_rolling_enrollment_cohort — training `rolling` enrollment carries the intake
  `cohort_start_date` (Phase 5 auto-fill from admission date → `2025-06-01`) and label `2025-06-01`.
- test_04_enrollment_searchable_by_cohort — `search([('cohort_kind','=','rolling')])` and
  `search([('grade_level_id','=',unit.id)])` each return the correct single enrollment (proves the
  stored relateds are searchable).

---

## GOTCHAS ENCOUNTERED (Phase 7)

1. **Faculty code must be LETTERS ONLY (re-hit)** — first draft used `'P7FS'` (digit `7`) →
   `ValidationError: Faculty code must contain only letters...` in `setUpClass`; fixed to `'PFSCI'`.
   Department codes still allow alphanumeric (`'P7MATH'` fine).
2. **Stored relateds are required for search/group** — `cohort_label` stays computed non-stored
   (display only); the 4 rollup fields are `store=True` relateds precisely so search/group_by work
   (Phase 4/6 lesson re-applied).
3. **Rollup is student-driven only** — the cohort comes from `student_id`, never from the offering or
   course, so existing (legacy and non-legacy) offerings can be reused in tests with no change.
4. The docutils "Unexpected indentation" ERROR lines during upgrade are **pre-existing** docstring
   warnings, not from Phase 7.

---

## EXIT CRITERIA — ALL MET

- [x] Legacy path unchanged — legacy enrollments untouched; existing `test_enrollment_model` suite green.
- [x] Rollup fields are stored relateds (searchable + groupable by cohort).
- [x] Zero regression: identical `6 failed, 3 error(s)` pre-existing set; 156→160 tests.
- [x] No behavior change to create/write/enroll flows — read-only derived data.
- [x] Upgrade applied to real `odoo` DB (`-u unicore_enrollment`), schema verified.

**Files touched:** `unicore/custom_addons/unicore_enrollment/{models/unicore_enrollment.py,
views/unicore_enrollment_views.xml, tests/__init__.py, tests/test_enrollment_cohort.py (new)}`.
**DBs:** upgraded `odoo` (real) and `odoo_p0_baseline` (migration bed).

**Open gap (NOT in Phase 7 scope):** `course.department_id` is still required for non-legacy schools —
schools need a department to create courses. Candidate for a later phase.
