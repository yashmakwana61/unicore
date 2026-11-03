---
id: documents
title: "Student documents and verification"
sidebar_position: 4
---
# Student documents and verification

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

Student documents are separately modeled as `edicai.student.document` and linked to a student, institution and campus.

## Declared document categories

Examples include ID proof, passport, visa, birth certificate, transcript, degree certificate, migration/transfer certificates, medical certificate, fee receipt and scholarship documentation.

Each document has a required **Document Name**, **Document Type**, **File**, and **Student** association. The model includes issue/expiry dates, issuing authority, reference and verification metadata.

## Verification controls

The source defines **Verify** and **Unverify** actions. Verification stores the current user and timestamp. Unverification clears them. An expiry date must be later than its issue date when both dates are present.

## Review protocol

1. Create only synthetic documents in a disposable database.
2. Open **Students → Documents** if this base menu is enabled.
3. Confirm document type and date validation on test files.
4. Review role-based access to binary attachments, downloads and verification actions.
5. Record whether a verification action is audit-logged and restricted as required by policy.

:::danger Privacy
Never upload student identity documents, health records or authentic certificates into public documentation screenshots, CI artifacts or developer test fixtures.
:::

**Sources:** [Document model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_student/models/edicai_student_document.py), [Document views](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_student/views/edicai_student_document_views.xml).
