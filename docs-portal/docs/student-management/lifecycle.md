---
id: lifecycle
title: "Student lifecycle and status changes"
sidebar_position: 3
---
# Student lifecycle and status changes

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

The student model defines a separate lifecycle from the admission applicant workflow.

## Declared states

| Status | Interpretation |
|---|---|
| Prospect | Possible future student |
| Admitted | Admission registered; default for new student record |
| Enrolled | Student has been enrolled |
| Active | Actively studying |
| On Leave | Temporary leave |
| Graduated | Graduation recorded |
| Alumni | Alumni status |
| Withdrawn | Withdrawal |
| Expelled | Expulsion |
| Deceased | Deceased record state, with restricted UI action |
| Cancelled | Cancelled |

## Actions exposed in the student form

| Action | Visible in the base form when |
|---|---|
| Enroll Student | Admitted |
| Activate | Enrolled |
| Place on Leave | Active |
| Return from Leave | On Leave |
| Graduate | Active |
| Convert to Alumni | Graduated |
| Withdraw | Admitted, Enrolled or Active |
| Expel | Active or On Leave |
| Cancel | Prospect, Admitted or Enrolled |
| Reactivate | Withdrawn, Expelled or Cancelled |

These conditions are extracted from XML button visibility. Server-side methods may contain further validations and the exact set of buttons is subject to inheritance, access rules and custom views.

:::warning
Status transitions mutate student records. Sensitive actions such as expulsion, death or cancellation must never be executed against real students for documentation testing.
:::

**Sources:** [Status model and actions](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_student/models/edicai_student.py), [Student form header](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_student/views/edicai_student_views.xml).
