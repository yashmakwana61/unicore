# Edicai ERP — Administrator Training Guide

> **Audience:** System administrators
> **Environment:** Edicai UAT (`http://127.0.0.1:18071`) — a clean, production-equivalent installation
> **How to use this guide:** Follow the modules in order. Each section walks through the real screens you will see, with screenshots taken from an actual session.

---

## Table of Contents

**Act I — Orientation & Setup** ✅
1. [Getting Started — Login, Home & the 17-Step Checklist](01_getting_started.md)
2. [Settings — Institution Setup, Users & Roles](02_settings_institution.md)
3. [Teaching I — Academic Calendar: Years, Semesters](03_teaching_calendar.md)
4. [Teaching II — Academic Structure: Faculties, Departments, Programs](04_teaching_structure.md)

**Act II — People & Operations** (in progress)
5. [Student Life — Students, Guardians & Discipline](05_student_life.md)
6. [Admissions — Cycles, Seats & the Applicant Pipeline](06_admissions.md)
7. [Finance — Fee Structures, Invoices & Payments](07_finance.md)
8. [Examinations — Schedules, Grading & Results](08_examinations.md)
9. [Campus Ops — Facilities, Transport & Appointments](09_campus_ops.md)
10. [Careers — Placement, Alumni & Scholarships](10_careers.md)
11. [Insights — Dashboards & Reports](11_insights.md)
12. [Comms & AI — Notifications, Notices & AI Tools](12_comms_ai.md)
13. Website & Apps — Overview *(next)*
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

## Known quirks found during the live walkthrough

| Quirk | Where | Status |
|---|---|---|
| Year fields display with thousand separators (`2,026`) | Company/Faculty/Student forms | Cosmetic — fix in field widget options |
| `[False] False` breadcrumb on unsaved Campus | Campuses New record | Cosmetic |
| Technical model names in breadcrumb on unsaved Guardian-Student Relationships | `edicai.guardian.student.rel` | Missing `_rec_name` — dev backlog |
| Applicant kanban shows "No stages yet" on fresh DB despite 13 stage records | Applicants | Investigate `edicai_admission` stage domain/cycle filter |
| `Esc` in edit mode discards the whole record | All forms | Odoo behaviour — train users to click away instead of Esc |
| Discipline "Reported By" needs a staff member; the inline quick-create modal targets HR departments | Discipline Records | Create staff via Institution → Faculty & Staff first |
| New fee lines inherit the previous row's Fee Type; totals refresh only after save | Fee Structures → Lines | Re-pick Fee Type per row before saving |
| Sales Journal dropdown only offers "Create" until the Institution is committed | Fee Accounting Configuration | Pick Institution from the dropdown first |
| `Send to Student` fails until an active Fee Accounting Configuration exists | Fee Invoices | Configure Finance → Fees → Configuration → Accounting Configuration |
| GL invoices stay in Draft when "Auto-Post to GL" is off; Record Payment is hidden until posted | Fee Invoices → GL Invoice | Open the GL Invoice and Confirm it |
| Hall tickets require the active attendance threshold (75% in the UAT policy) and no unpaid fee invoices | Examinations → Generate Hall Tickets | Read the eligibility note, resolve the source record, then regenerate; do not use override for routine issuance |
| Timetable-entry and grade-entry relational selectors can show only "Create" when the related Institution field is still empty | Timetable Entries; Grade Entry | Do not create duplicate offerings/enrollments; report the selector/domain issue for a UI fix |
| Closing an attendance session after marking can fail during the attendance-statistics recompute | Attendance Sessions | Preserve the attendance records and report the error; ticket eligibility still evaluates the recorded attendance |
| Semester Results generation has no normal UI button in this build | Grading → Semester Results | The list/publish form is available; ask an administrator/developer to run the supported generation operation if no result is listed |
| Appointment Slot save raises Access Error for Administrator in the clean UAT database, despite an appointment-admin ACL being present | Comms & AI → Appointments → Slots | No slot was created; investigate effective permissions through the approved access process and do not weaken ACLs |
| Alumni add-on has no standalone Alumni register; it extends Student with mailing-list/event links | Student record | Keep the existing student identity and manage relationships through its alumni smart buttons |
| Edicai AI shows Provider unavailable in this UAT workspace | Comms & AI → Edicai AI | Treat AI answers as unavailable until an approved provider is configured and tested; never paste private data into an unverified service |
| Notification log rows may say Sent while external provider/inbox delivery is not verified | Comms & AI → Notifications | Check failed notifications and the provider/channel audit separately; confirm receipt before relying on a communication |
| Insights → Dashboards includes general Odoo gallery tiles with seeded/demo-looking figures, not Edicai student KPIs | Insights → Dashboards | Use Insights → Analytics for Edicai enrollment, attendance, grades, fees and admissions; confirm filters before interpreting values |

## The Edicai Workspace Map

| Workspace | What lives there |
|---|---|
| 🏠 Home | Personal dashboard, KPIs, setup progress |
| 🏛️ Institution | Institution profile, campuses, academic structure & calendar |
| 🧑‍🤝‍🧑 Admissions | Cycles, applicants, entrance tests, offer letters |
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
