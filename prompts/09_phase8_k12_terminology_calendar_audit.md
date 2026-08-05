# Phase 8 — K-12 Terminology + Academic Calendar Terms (Verification Audit)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Status:** COMPLETE (2026-08-05) — ZERO REGRESSION, 9 new tests green, migration verified on real DB.
**This is the capstone of the 8-phase migration.**

---

## ROLE

You are a senior Odoo architect on UniCore. Phase 8 closes the multi-entity story with two additive,
**legacy-inert** capabilities:

1. **Terminology actually works.** `unicore.terminology.profile` existed but was never consumed.
   Phase 8 adds a label-resolution API so a K-12 school resolves "Class/Section", "Term", "Session",
   "Teacher", "Learner" instead of "Program", "Semester", "Academic Year", "Faculty", "Student".
2. **A real K-12 Term calendar.** `unicore.academic.year` gains a `Term Based` structure and
   `unicore.semester` gains `First/Second/Third/Fourth Term` types, with enforcement that a Term year
   contains only Term semesters.

Hard exit criteria:
1. Legacy path 100% unchanged — university vocabulary and semester-based years untouched.
2. Terminology resolution is a pure helper + read-only preview; no static view labels change.
3. Zero regression on the full suite (identical pre-existing failure set: `6 failed, 3 error(s)`).
4. The tag list expansion (`/unicore_calendar` added) is deliberate and recorded.

---

## WHAT CHANGED

### Part A — Terminology (`unicore/custom_addons/unicore_institution_profile/`)

**`models/unicore_terminology_profile.py`**
- `_TERM_CONCEPTS` class constant: `concept -> (term field, generic fallback)` for
  `faculty`, `department`, `program`, `student`, `faculty_staff`, `semester`, `academic_year`.
- `resolve_label(concept, default=None)` — profile's substituted label, else `default`, else the
  generic term; unknown concepts resolve to `default` or the concept key.
- `label_summary` — computed (non-stored) Char, `depends` on every `term_*` field, rendered as a
  `Generic → Applied` preview on the terminology form (new "Applied Labels (read-only preview)" group).

**`models/res_company.py`**
- `get_term_label(concept, default=None)` — resolves through the stored related
  `terminology_profile_id`; no profile → `default` (legacy output unchanged).

**`models/unicore_institution_profile.py`**
- `calendar_mode` adds `('term', 'Term Based')`.

**`data/unicore_institution_profile_data.xml`** (both `noupdate=1`, inert until attached)
- `terminology_school_k12` (K12): faculty blank (hidden), department `Grade Level`, program
  `Class/Section`, student `Learner`, faculty_staff `Teacher`, semester `Term`, academic_year `Session`.
- `profile_school_k12` (K12_SCHOOL): `school`, `is_legacy_university False`, `calendar_mode term`,
  `grading_scheme simple_percentage`, terminology linked, `academic_unit_level_ids` = [Grade Level]
  only, feature subset.

### Part B — Calendar Terms (`unicore/custom_addons/unicore_calendar/`)

**`models/unicore_academic_year.py`**
- `year_type` adds `('term', 'Term Based')`.
- `_TERM_SEMESTER_TYPES = ('term_1', 'term_2', 'term_3', 'term_4')`.
- `_check_term_structure()` + `create()`/`write()` overrides (`write` checks when `year_type` or
  `semester_ids` in vals): a Term-based year may only contain Term semesters. Legacy-inert — only
  fires when `year_type == 'term'` is set explicitly.

**`models/unicore_semester.py`**
- `semester_type` adds `term_1..term_4`.
- `@api.constrains('academic_year_id', 'semester_type') _check_term_semester_type()` — covers direct
  semester creation on a Term year (complements the year-level check).

---

## VERIFICATION (migration + zero regression)

### Migration path tested on an OLD-schema DB first
`-u unicore_institution_profile,unicore_calendar` on **`odoo_p0_baseline`** and on the real **`odoo`** DB.

| Check | Result |
|---|---|
| Upgrade exit code | EXIT=0 (both DBs) |
| ERROR/CRITICAL lines | 0 CRITICAL / 0 non-benign ERROR (both DBs; only the pre-existing docutils + duplicate-key cleanup lines) |
| Seeds | `terminology_school_k12` + `profile_school_k12` loaded (verified by `env.ref` in tests) |

### Zero regression — identical failure set
Full 19-module suite (with `/unicore_calendar` added to the tag list) on the real `odoo` DB:

```
6 failed, 3 error(s) of 169 tests
```

The **9 failures are exactly the pre-existing set** (unchanged since Phase 0):
- `unicore_fees` — test_04, test_05, test_06, test_08 (ERROR), test_09
- `unicore_api` — test_14_current_semester
- `unicore_admission` — test_14_record_fee_payment (FAIL), test_12_publish_grade (ERROR)
- `unicore_website` — setUpClass error

Test count grew 160 → **169** (+5 terminology + 4 calendar). Isolated run
(`/unicore_institution_profile,/unicore_calendar`): **0 failed, 0 errors of 25 tests**
(16 existing + 5 new + 4 new calendar).

> **Scope decision (flagged):** `/unicore_calendar` was added to the full-suite tag list (18 → 19
> modules) — the same precedent as Phase 2 adding `/unicore_curriculum`. `unicore_calendar` previously
> had no tests.

### Phase 8 tests
- `unicore_institution_profile/tests/test_terminology.py` (NEW, 5): legacy resolve defaults; blank-term
  fallback; company resolution (no profile → default/None, legacy → unchanged, school → K-12 vocab);
  K-12 seed profile wiring; `label_summary` preview.
- `unicore_calendar/tests/test_academic_calendar_term.py` (NEW, 4): Term year + 3 Term semesters ok;
  Term year rejects odd semester (via o2m write and direct create); switching a semester year to Term
  rejected; legacy semester year unchanged (and may use Term types).

---

## GOTCHAS ENCOUNTERED (Phase 8)

1. **Term enforcement needs two hooks.** Changing `year_type` on a year with existing odd semesters is
   only caught by the year's `write()` override (semester `@api.constrains` won't re-fire, since
   `academic_year_id` didn't change). Direct `semester.create` is only caught by the semester
   `@api.constrains`. Both are needed for full coverage — tests exercise both paths.
2. **`_check_overlap_active` on academic.year** — test years must be created with `year_state='cancelled'`
   to avoid overlap validation with any existing active year.
3. **Seeds are inert by design** — `profile_school_k12` is `is_legacy_university False`, but nothing
   reads it until a company attaches it; the legacy company (no profile) is 100% unchanged.
4. Terminology stays a **helper + preview**, not wired into static Odoo view field labels (that would
   require dynamic `get_views` rewriting — intentionally out of scope).

---

## EXIT CRITERIA — ALL MET

- [x] Legacy path unchanged — university vocabulary + semester years untouched; existing suites green.
- [x] Terminology is a pure resolver + read-only preview; no static label behavior changed.
- [x] Zero regression: identical `6 failed, 3 error(s)` pre-existing set; 160→169 tests (9 new).
- [x] Tag-list expansion (`/unicore_calendar`) deliberate + recorded.
- [x] Upgrade applied to real `odoo` DB (`-u unicore_institution_profile,unicore_calendar`), seeds verified.

**Files touched:**
- `unicore_institution_profile/{models/unicore_terminology_profile.py, models/res_company.py,
  models/unicore_institution_profile.py, data/unicore_institution_profile_data.xml,
  views/unicore_terminology_profile_views.xml, tests/__init__.py, tests/test_terminology.py (new)}`
- `unicore_calendar/{models/unicore_academic_year.py, models/unicore_semester.py,
  tests/__init__.py (new), tests/test_academic_calendar_term.py (new)}`

**DBs:** upgraded `odoo` (real) and `odoo_p0_baseline` (migration bed).

---

## 8-PHASE MIGRATION — COMPLETE

Test trajectory: `100 → 116 → 122 → 137 → 144 → 149 → 152 → 156 → 160 → 169`, with the identical 9
pre-existing failures throughout and ZERO regression at every step.

**Open gaps (post-8, not in scope):** `course.department_id` still required for non-legacy schools;
terminology not wired to static view labels; admission-cycle cohort binding; report/portal cohort
filters; graduation/convocation cohort grouping.
