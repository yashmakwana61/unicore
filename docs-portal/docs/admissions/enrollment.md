---
id: enrollment
title: "Program enrollment & course registration"
sidebar_position: 5
---
# Program enrollment & course registration

> **Review status: Source-reviewed draft.** Exact UI routes, behaviors and screenshots require isolated runtime verification.

Edicai distinguishes **program-level admission enrollment** from **course-level registrations**.

| Record | Responsibility |
|---|---|
| `edicai.admission.enrollment` | Links applicant and student to a program, campus, cycle, academic year and semester |
| `edicai.enrollment` | Tracks student registration in individual course offerings |

## Prerequisites in the source

Program enrollment references an existing applicant and linked student, program, campus, academic year, semester/term and admission cycle.

### Program enrollment states

- **Pending:** initial state
- **Enrolled:** student has progressed to enrolled status
- **Completed:** enrollment period closed
- **Withdrawn:** withdrawn status is available in the model
- **Cancelled:** cancelled status

The model defines actions including **Mark Enrolled**, **Mark Completed**, and **Cancel**. The applicant form also defines an **Enroll in Program** action, displayed only for confirmed applicants with a linked student.

## Proposed demo-only verification

1. Confirm a synthetic applicant and check that a corresponding student exists.
2. Open **Enroll in Program** and capture a screenshot of the wizard.
3. Select only test campus, program, term and course offerings.
4. Complete the wizard in an isolated database; inspect generated program enrollment and course registrations.
5. Confirm duplicate enrollment, eligibility, permission and capacity safeguards before publication.

:::warning
Course conflicts, prerequisites and capacity limits are business-critical. This article documents model relationships, **not successful operation** of all enrollment validations.
:::

**Source evidence:** [Program enrollment model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/models/admission_enrollment.py), [course enrollment model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/models/edicai_enrollment.py), [enrollment wizard](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/wizards/admission_enrollment_wizard.py).
