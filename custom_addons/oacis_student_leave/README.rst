Oacis Student Leave Requests
==============================

A formal, student/guardian-initiated leave request
workflow for Oacis ERP.

Overview
--------

This module provides a leave request submission
system that is **distinct** from the registrar-side
"Place on Leave" button already on ``oacis.student``.

Students or guardians can **submit** a leave request
with:

- Reason for leave
- Start and end dates
- Supporting documents

The request routes to faculty/registrar for approval.
On approval, the existing ``action_place_on_leave``
method on ``oacis.student`` is triggered, keeping
this module additive.

Features
--------

- **Portal-based submission** — Students and guardians
  can submit requests via the self-service portal
- **Backend review workflow** — Faculty, registrar
  and admin can review, approve or reject requests
- **Multi-channel notifications** — Email, WhatsApp
  and in-app notifications on submit/approve/reject
- **Automatic leave trigger** — Approval calls the
  existing ``action_place_on_leave`` on the student
  record
- **Supporting documents** — Upload medical
  certificates or other documentation
- **Activity-based routing** — Approval activities
  created for registrar users

States
------

1. **Draft** — Request created, not yet submitted
2. **Submitted** — Sent for approval; activity
   assigned to registrar
3. **Approved** — Approved by registrar; student
   placed on leave automatically
4. **Rejected** — Rejected with notes; student
   can resubmit
5. **Cancelled** — Cancelled by student or guardian

Dependencies
------------

- ``oacis_student`` — Student profile and
  ``action_place_on_leave``
- ``oacis_guardian`` — Guardian profiles and
  ward relationships
- ``oacis_notify`` — Multi-channel notification
  engine
- ``oacis_portal_student`` — Student portal
  infrastructure
- ``oacis_portal_guardian`` — Guardian portal
  infrastructure

Integration
-----------

On approval, this module calls the **existing**
``action_place_on_leave`` method on
``oacis.student`` rather than duplicating the
state machine. This keeps the module fully additive.

Portal Routes
-------------

- ``/my/oacis/student/leave`` — List leave
  requests
- ``/my/oacis/student/leave/new`` — Create new
  request
- ``/my/oacis/student/leave/<id>`` — View request
  details
