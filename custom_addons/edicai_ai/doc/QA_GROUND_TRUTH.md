# Conversational ERP — Manual QA Ground Truth

This document belongs to the **manual-testing lab** (not a business
feature). It lists the deterministic dataset created by
**Settings → Edicai AI → Manual QA Toolkit → "Create QA Dataset"**
(admin-only) and the exact answers **according to Odoo** that a tester
should compare every AI answer against.

Run the companion live report (the values recomputed from Odoo at
query time) from an Odoo shell as manager:

```python
env['edicai.ai.qa.toolkit'].qa_ground_truth_report()
```

## Dataset codes (searchable in the backend)

| Object | Code / marker |
| --- | --- |
| Campus | `QALAB` ("QA Lab Campus") |
| Faculty / Department | `QALABF` / `QALABD` |
| Program / Course | `QALABP` / `QALABC` |
| Academic year / semester | `QALABY` (2030-07-01…) / `QALABS1` |
| Building / Room | `QALABB` / `QALABR` |
| Course offering | course QALABC × semester QALABS1 × campus QALAB |
| Timetable slot / room | "QA Lab Slot" (07:00–08:00) / `QALABR` |
| Attendance policy | "QA Lab Policy 80/85" (min 80%, warning 85%, exam-eligibility linked) |
| Students | **TEST-STUDENT-001** (login `qa_student`), TEST-STUDENT-002 |
| Admission applicant | TEST-APPLICANT-001 (`test.applicant.001@qa.example.edu`, state `applied`) |
| Asset request | description "QALAB projector", state `draft` |

## Ground-truth answers (what Odoo says)

| Question | Correct answer according to Odoo |
| --- | --- |
| Attendance of TEST-STUDENT-001 | 4 held sessions — 3 present, 1 absent → **75.0%** |
| Attendance policy minimum | **80%** (warning 85%, exam-eligibility linked) |
| Is TEST-STUDENT-001 short? | **YES** (75.0% < 80%) — flagged by `shortage_alert`, severity HIGH |
| Is TEST-STUDENT-002 short? | **NO** (100.0%) |
| Outstanding fee of TEST-STUDENT-001 | **12,500.00** (QT "QA Lab" tuition invoice, due 2030-09-01) |
| Program of TEST-STUDENT-001 | QA Lab Program (`QALAB-P`) |
| Campus of TEST-STUDENT-001 | QA Lab Campus (`QALAB`) |
| Open applicants | TEST-APPLICANT-001 in state `applied` |
| Draft asset requests | 1 ("QALAB projector") |

## Notes

* All dataset records carry the QALAB marker, so they can be located
  and (if ever needed) removed by hand — the toolkit's reset function
  deliberately does **not** delete business records.
* Percentages/figures in the AI answers must match this table
  **exactly**; any mismatch is an AI grounding defect to report.
* The student persona (`qa_student`) is portal-grouped and linked to
  TEST-STUDENT-001 — the conversational chatbot is staff-only by
  design, so the student persona exercises *security* (no data) rather
  than chat.
