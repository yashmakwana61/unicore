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

**Act II — People & Operations** *(not yet documented; planned)*
5. Student Life — Students, Guardians & Hostels
6. Admissions — Pipeline & Applicant Conversion
7. Finance — Fee Structures, Invoices & Payments
8. Examinations — Schedules, Grading & Results
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
```

`Draft → Confirmed/Operational/Approved → Active/Current` workflows appear everywhere — always confirm top rows first, then activate children.

## Training evidence and scope

The four Act I chapters and their screenshots were captured in a UAT browser walkthrough on 2 November 2026. They demonstrate this particular university-style setup, not every institution configuration. They do not establish that the unfinished Act II workflows have been tested. The Home “Getting Started” checklist is a demo/onboarding feature and **is not required** to perform the administrator setup steps below.

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
