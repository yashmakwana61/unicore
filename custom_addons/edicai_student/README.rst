Edicai Student Management
==========================

This module provides complete student lifecycle management for Edicai ERP.

Features
--------
* Student profiles with personal, contact, and identification details
* Multi-company and multi-campus isolation
* Academic placement (program, specialisation, batch year)
* Academic performance tracking (GPA, credits, completion %)
* Document management with verification workflow
* Emergency contact / guardian management
* Academic history per semester/year
* 11-state student lifecycle (Prospect → Admitted → Enrolled → Active → ... → Alumni)
* Status change wizard for transitions requiring a reason
* Auto-generation of student ID numbers
* Auto-creation of partner record (for portal access)
* Mail threading and activity tracking on all models
* Full record rules with company, campus, and self-view isolation

Dependencies
------------
* edicai_base
* edicai_security
* edicai_campus
* edicai_academic
* edicai_calendar

Models
------
* edicai.student — Core student record
* edicai.student.document — Document management
* edicai.student.emergency.contact — Emergency contacts / guardians
* edicai.student.academic.history — Semester-wise academic records
* edicai.student.status.wizard — Status change reason wizard

Security Groups
---------------
All 7 groups from edicai_base with granular permissions:
* Admin/Manager: Full CRUD on all models
* Registrar: Full CRUD on student, document, contact, history
* Finance: Read student + CRUD documents and history
* Faculty/Staff: Read-only on all models
* Student: Read-only on own records only
