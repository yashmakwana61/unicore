---
id: overview
title: "Admissions overview"
sidebar_position: 1
---
# Admissions overview

> **Review status: Source-reviewed draft.** Exact UI routes, behaviors and screenshots require isolated runtime verification.

Edicai's admission source contains an admission cycle, applicant pipeline, entrance tests, offer letters, program enrollment records, and course-level enrollment records.

## Who this guide is for

Admissions administrators and registrars. The exact permissions and menu location must be verified against the configured institution database. The base menu records identify the Admissions root, but the optional navigation preview may move this section into a workspace.

## Underlying records

| Area | Technical model |
|---|---|
| Cycles | `edicai.admission.cycle` |
| Applicants | `edicai.admission.applicant` |
| Program enrollments | `edicai.admission.enrollment` |
| Course enrollments | `edicai.enrollment` |
| Offer letters | `edicai.admission.offer.letter` |
| Entrance tests | `edicai.admission.entrance.test` |

## Source-evidenced workflow

1. Configure a campus, academic year, programs and admission seats.
2. Create and activate an admission cycle.
3. Create applicant records and move applications through review stages.
4. Shortlist and generate a merit list using configured scoring weights.
5. Issue and review offer letters.
6. Confirm admission and create a linked student record.
7. Enroll the student in a program, term and course offerings, when eligible.

These are *source-documented capabilities*, not a tested live end-to-end procedure. The existing [student-lifecycle audit](https://github.com/yashmakwana61/unicore/blob/main/docs/STUDENT_LIFECYCLE_WORKFLOW.html) records significant cross-module workflow gaps. Do not use this page as evidence that automation, fees, or institutional enrollment are working reliably.

## Explore the guides

- [Admission cycles](./cycles.md)
- [Applicant review and merit](./applicants.md)
- [Offers and student confirmation](./offers.md)
- [Program enrollment](./enrollment.md)
- [Verification status and screenshot plan](./verification.md)

Source: [Admission addon](https://github.com/yashmakwana61/unicore/tree/main/custom_addons/edicai_admission).
