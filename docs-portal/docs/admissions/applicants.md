---
id: applicants
title: "Applicants, reviews & merit"
sidebar_position: 3
---
# Applicants, reviews & merit

> **Review status: Source-reviewed draft.** Exact UI routes, behaviors and screenshots require isolated runtime verification.

The applicant model holds identity and contact details, program/campus choices, academic scores, document flags, guardians and stage/status information.

## Pipeline states in the source

`Inquiry → Applied → Documents Pending → Under Review → Shortlisted → Entrance Scheduled → Merit Listed → Offer Sent → Fee Pending → Confirmed`.

Other available outcomes include **Rejected**, **Withdrawn**, and **Waitlisted**. The sequence above is a conceptual happy path; not every application necessarily follows every intermediate state.

## Source-defined UI actions

| Applicant state | Button defined on the source form |
|---|---|
| Inquiry | Apply |
| Applied | Submit Documents |
| Documents Pending | Submit for Review |
| Under Review | Shortlist |
| Shortlisted | Schedule Entrance |
| Shortlisted / Entrance Scheduled | Add to Merit |
| Merit Listed | Send Offer |
| Fee Pending | Confirm Admission |
| Confirmed with linked student | Enroll in Program |

Other buttons include **Reject**, **Withdraw**, **Waitlist**, and **Advance to Next Stage**, with visibility conditions.

## Proposed verification procedure

1. On a disposable Edicai demo, open the **Applicants** screen as an authorized test registrar.
2. Create an applicant linked to a synthetic admission cycle, campus and program; use no real personally identifiable data.
3. Review **Personal**, **Scores**, **Documents**, **Guardian**, and **Offer Letters** tabs in the applicant form.
4. For each state, record which action buttons are visible and compare the observed transition with the source model.
5. Review the list and Kanban presentations, including stage grouping.
6. Validate a synthetic candidate's composite score, merit rank and state changes.

:::warning
**Submit for Review**, **Shortlist**, **Add to Merit** and **Send Offer** change records. Verify on a disposable synthetic demo only. A visible UI action is not proof that all underlying authorization and workflow checks succeeded.
:::

**Source evidence:** [Applicant model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/models/admission_applicant.py), [form and Kanban views](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/views/admission_applicant_views.xml), [menu records](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/menus/admission_menus.xml).
