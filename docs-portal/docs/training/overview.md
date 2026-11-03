---
title: Administrator Training — Overview
sidebar_position: 1
---

# Edicai ERP — Administrator Training Guide

> **Audience:** System administrators
> **Environment:** Edicai UAT — a clean training instance. The localhost URL shown in the source guide is environment-specific; use the address provided by your administrator.
> **How to use this guide:** Follow the modules in order. Each section walks through the real screens you will see, with screenshots taken from an actual session.

---

## Table of Contents

**Act I — Orientation & Setup**
1. [Getting Started — Login, Home & the 17-Step Checklist](01_getting_started.md)
2. [Settings — Institution Setup, Users & Roles](02_settings_institution.md)
3. [Teaching I — Academic Calendar: Years, Semesters](03_teaching_calendar.md)
4. [Teaching II — Academic Structure: Faculties, Departments, Programs](04_teaching_structure.md)

**Act II — People & Operations** *(in progress)*
5. [Student Life — Students, Guardians & Discipline](05_student_life.md)
6. [Admissions — Cycles, Seats & Applicant Pipeline](06_admissions.md)
7. [Finance — Fee Structures, Invoices & Payments](07_finance.md)
8. [Examinations — Schedules, Hall Tickets, Grading & Results](08_examinations.md)
9. Campus Ops — Facilities, Transport & Appointments
10. Careers — Placement, Alumni & Scholarships
11. Insights — Dashboards & Reports
12. Comms & AI — Notifications & AI Tools
13. Website & Apps — Overview
14. Quick Reference Cheat Sheet

---

## The Golden Setup Rule

Edicai enforces a top-down dependency chain. Whenever you see **"Invalid Operation"** during go-live, it means a required parent is missing:

```
Company (Institution Details)
  └─→ Campus  (+Building)
        └─→ Faculty
              └─→ Department
                    └─→ Program  (+Campus assignment)
                          └─→ Courses / Offerings / Sections
                          └─→ Academic Year → Semester
                                └─→ Admission Cycle (+Seat allocation)
                                      └─→ Applicant pipeline → Student → Fees → Classes
```

`Draft → Confirmed/Operational/Approved → Active/Current` workflows appear everywhere — always confirm top rows first, then activate children.

## Training evidence and scope

Chapters 1–8 are based on UAT browser walkthroughs conducted on 2–3 November 2026. They demonstrate a university-style setup rather than every institution configuration. Student Life and Admissions include partial workflows and recorded validations. The Finance and Examinations chapters document end-to-end UAT examples, with important accounting, attendance, relational selector and semester-result limitations noted; do not treat these examples as production certification. The Home “Getting Started” checklist is a demo/onboarding feature and **is not required** to perform the administrator setup steps below.

## Additional finance and examination observations

- New Fee Structure lines may inherit the preceding Fee Type; reselect the type on each line and verify totals after saving.
- Fee invoices require an active, institution-specific accounting configuration to generate a GL invoice; when auto-posting is off, post the GL invoice before recording payments.
- Hall-ticket eligibility uses the configured attendance and outstanding-fee policies (75% attendance in the recorded UAT example).
- Attendance session closure, some relational selectors, and semester-result generation have known UI limitations in the UAT build; follow the chapter cautions and escalate errors rather than editing records directly.

## Known UAT observations

- The unsaved Guardian–Student relationship can show a technical model name in its breadcrumb.
- Applicants can display “No stages yet” in an empty kanban even when admission stage records exist; the cause has not been fully verified.
- An Admissions Cycle cannot be activated without program seat allocation.
- A Discipline record's “Reported By” requires a staff/faculty record; the inline quick-create flow uses HR department fields.

## The Edicai Workspace Map

| Workspace | What lives there |
|---|---|
| 🏠 Home | Personal dashboard, KPIs, setup progress |
| 🏛️ Institution | Company/institution profile, campuses, academic structure, calendar |
| 🧑‍🤝‍🧑 Admissions | Applicants, admission funnel, entrance tests |
| 🎓 Student Life | Students, guardians, hostel, library, discipline |
| 📚 Teaching | Faculties, departments, programs, courses, timetables |
| 📝 Examinations | Exam schedules, grading, gradebook, results |
| 💰 Finance | Fee structures, invoices, payments, accounting |
| 🏢 Campus Ops | Buildings, facilities, transport, appointments |
| 💼 Careers | Placement, alumni, scholarships |
| 📊 Insights | Analytics dashboards and reports |
| 🌐 Website | Public website (Odoo default) |
| 🤖 Comms & AI | Notifications, notice board, AI tools |
| 🧩 Apps / ⚙️ Settings | Module management and system configuration |

---
