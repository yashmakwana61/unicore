---
id: offers
title: "Offer letters & admission confirmation"
sidebar_position: 4
---
# Offer letters & admission confirmation

> **Review status: Source-reviewed draft.** Exact UI routes, behaviors and screenshots require isolated runtime verification.

The application pipeline includes offer letters and a final confirmation step, with student records linked to confirmed applicants.

## Source-evidenced sequence

1. When an applicant reaches **Merit Listed**, the form exposes **Send Offer**.
2. The source lifecycle test expects that operation to create an offer letter and transition the applicant to **Offer Sent**.
3. The test then exercises the offer letter's **Send** and **Accept** operations.
4. On offer acceptance, the test expects the applicant to enter **Fee Pending**.
5. The applicant form exposes **Confirm Admission** in the Fee Pending state.
6. The source test expects confirmation to create and link an `edicai.student` record.

The above expectations are traceable to repository code and tests. They **have not** been verified against the live application in this documentation project.

## Manual verification checklist

- [ ] Offer template renders correctly without real applicant data
- [ ] Offer is generated once and correctly associated with the applicant
- [ ] Offer sending does not deliver messages outside the test environment
- [ ] Acceptance and rejection transitions are consistent
- [ ] Fee validation requirements are checked before final confirmation
- [ ] Student creation is idempotent and restricted to authorized roles
- [ ] Applicant, student and fee records link consistently

:::danger Financial and identity-sensitive workflow
Do **not** use an actual institution's applicants, real payment integrations or external email services during documentation testing. The existence of the **Confirm Admission** action does not establish that fee settlement or eligibility checks have been completed.
:::

**Source evidence:** [Applicant actions](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/models/admission_applicant.py), [offer letter model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/models/offer_letter.py), [admission lifecycle tests](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/tests/test_admission_to_enrollment_workflow.py).
