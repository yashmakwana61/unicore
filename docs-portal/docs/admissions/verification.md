---
id: verification
title: "Admissions verification & screenshots"
sidebar_position: 6
---
# Admissions verification & screenshots

> **Review status: Source-reviewed draft.** Exact UI routes, behaviors and screenshots require isolated runtime verification.

This Admissions pilot contains **source-evidenced draft guidance**, not complete runtime-approved instructions.

## Runtime verification requirements

- Disposable or isolated Edicai instance with a reviewed code revision
- Synthetic campus, academic year, programs, cycle and applicants
- Registrar/admin test roles with least-privilege access
- Outbound email, SMS, payment collection and other external effects disabled
- No production students, staff, contact details or financial records

## What requires screenshots

| Screen | Screenshot | Review status |
|---|---|---|
| Admission cycles list | Pending | Not runtime-verified |
| Cycle form with seat allocation | Pending | Not runtime-verified |
| Applicant form | Pending | Not runtime-verified |
| Applicant Kanban stages | Pending | Not runtime-verified |
| Offer letter form | Pending | Not runtime-verified |
| Program enrollment wizard | Pending | Not runtime-verified |
| Enrollment records | Pending | Not runtime-verified |

## Safe capture automation

A Playwright harness in `docs-portal/verification/` can take screenshots of a **pre-authorized, disposable** Edicai environment after manually configured authentication. It must never create, edit or delete Odoo records, even when identifying a page fails.

The harness is deliberately guarded against production-like hostnames and runs only with an explicitly set expected demo origin. Screenshots must be manually examined for privacy and correctness before adding them to the public docs.

## Approval gate

**Draft → Source reviewed → Runtime verified → Screenshot reviewed → Approved → Published**.

Changes to routes, model permissions, admission actions or workflow states invalidate relevant approvals.

See [workflow testing source](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/tests/test_admission_to_enrollment_workflow.py) and [student lifecycle audit](https://github.com/yashmakwana61/unicore/blob/main/docs/STUDENT_LIFECYCLE_WORKFLOW.html).
