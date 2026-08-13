Oacis Student Management
==========================

This module provides complete student lifecycle management for Oacis ERP.

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
* oacis_base
* oacis_security
* oacis_campus
* oacis_academic
* oacis_calendar

Models
------
* oacis.student — Core student record
* oacis.student.document — Document management
* oacis.student.emergency.contact — Emergency contacts / guardians
* oacis.student.academic.history — Semester-wise academic records
* oacis.student.status.wizard — Status change reason wizard

Security Groups
---------------
All 7 groups from oacis_base with granular permissions:
* Admin/Manager: Full CRUD on all models
* Registrar: Full CRUD on student, document, contact, history
* Finance: Read student + CRUD documents and history
* Faculty/Staff: Read-only on all models
* Student: Read-only on own records only
