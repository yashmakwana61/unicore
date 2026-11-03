# 14. Quick Reference — Administrator Cheat Sheet

Use this page for the short version. For details, screenshots and warnings, follow the linked chapter.

## 14.1 Golden rules

1. **Company → Campus/Buildings/Floors → Faculties → Departments → Programs → Courses → Offerings**. If a record needs a missing parent, stop and create that parent first.
2. **New records start in Draft.** Advance them deliberately: `Draft → Approved/Confirmed/Operational → Active/Current`.
3. **Parent-tainted values do not match until committed.** Type the parent value, choose it from the dropdown, and confirm it is saved before relying on filtered child dropdowns.
4. **Do not use the clean UAT sample as production content.** Seeded approvals, random names and default website pages are there to exercise the workflow.
5. **UAT and production are separate change paths.** Test the whole flow in UAT/staging, then release with an approved change log and backup.
6. **Do not weaken ACLs or security to get a button working.** Diagnose the effective permission set, Groups and record ownership instead.
7. **When a role step fails, stop and report.** Preserve the record, screenshot the error, and attach the module/action/user/time details.

## 14.2 Go-live sequence

| Phase | Do this | Verify |
|---|---|---|
| 1. Foundation | Institution profile, logo, addresses, tax/registration details, users and roles | Admin can log in; roles see intended menus |
| 2. Campus | Campuses, buildings, floors, rooms, facilities | Security and room capacity data match |
| 3. Academic calendar | Academic years and semesters | Current year/semester selected |
| 4. Structure | Faculties, departments, programs, courses, offerings | Draft/Approved/Active states all advance |
| 5. Admissions | Cycle, seat allocations, application stages, entrance/offer letters | Applicant appears in enrollment view |
| 6. Student lifecycle | Student/guardian/emergency records, enrollments, hostel/transport as used | Student is enabled and linked to guardian |
| 7. Fees | Fee structures, accounting config, invoices, GL posting, payment reconciliation | Invoice and GL statuses agree |
| 8. Attendance/Exams | Timetable/session, attendance, hall tickets, seating, grades, results | Attendance and fee gates pass; results published deliberately |
| 9. Operations | Appointments, transport, scholarships, placements | Assignments work; no cross-institution visibility |
| 10. Public/comms | Maintenance, notices, website/Apps/AI checks | No placeholder or unapproved external content |

See: [Getting Started](01_getting_started.md) · [Settings](02_settings_institution.md) · [Academic Calendar](03_teaching_calendar.md) · [Academic Structure](04_teaching_structure.md).

## 14.3 Daily administrative runbook

### Every morning

- Check home KPIs for resolution items and pending workflows.
- Check **Failed Notifications** and investigate delivery failures.
- Check outstanding invoices and GL postings that remain in Draft.
- Check Hall/grade progress before exams or result publication.
- Confirm backups are healthy and restore-test recently.

### Before an exam or deadline

1. Verify the course offering and roster.
2. Confirm attendance and unpaid-fee eligibility.
3. Regenerate hall tickets, approve eligible tickets, generate seating.
4. Verify venue, exam instructions, exam date/times, roster and seat labels.
5. Post notice only after approval; check inactive/expired delivery.
6. Keep grading and results in their separate workflows.

### Student exit/change

- Use the student lifecycle screens, not database edits.
- Update guardian/contact links and any transport/hostel/fee obligations.
- Re-check consent, safeguarding and records retention before archive.
- Document the reason and effective date; student-facing services stop as configured.

## 14.4 Common faults and safe fixes

| Symptom | Likely cause | Safe action |
|---|---|---|
| **Invalid Operation** during setup | Missing parent in the dependency chain | Create/activate the parent; do not bypass validation |
| Parent dropdown only shows **Create** | Parent value typed but not committed or filtered by same institution/company | Choose the exact parent record, save, then retry |
| Saved fee lines inherit previous Fee Type | Grid rows retain row state | Re-pick type per line and save |
| `Send to Student` blocked | No active Fee Accounting Configuration or wrong journal/account | Configure Finance → Fees → Configuration first |
| GL invoice stays Draft | Auto-Post is off | Open GL Invoice and post it manually |
| Eligibility is False | Attendance below policy or unpaid fees | Fix source record; do not routine override |
| Closing attendance fails recompute | Product defect in stats recompute | Keep records; report error; verify grades with cross-check |
| Grade Entry selector says only **Create** | Related Institution not committed/filter defect | Do not create duplicates; report UI selector bug |
| Appointment slot raises Access Error | Effective permissions/ACL defect despite admin ACL | Stop; investigate groups and record scope; do not loosen ACLs |
| Semester Results empty | Generation not exposed as normal UI button | Ask administrator/developer to run supported generation operation |
| Website shows default content | Setup incomplete | Replace and approve before public release; do not provide as institution site |
| Edicai AI unavailable | Provider unset, unsupported, offline or not tested | Treat as unavailable until provider is configured and validated |
| Notification status **Sent** but no inbox email | Local/channel record not external receipt | Check failed notifications and provider; confirm actual recipient receipt |

## 14.5 Security and support escalation

1. Capture: institution, exact screen/menu, record ID, timestamp, screenshot, error text.
2. Note user, groups and whether the user is an administrator.
3. Check no security rule or record scope was changed before the issue.
4. If unsure, leave the record in Draft/inactive and escalate to the product administrator.
5. For suspected data loss or breach, stop changes and follow incident response immediately.
6. Never share secrets, passwords, or full student records in tickets, AI prompts or chat.

## 14.6 Documentation map

| Chapter | Outcome |
|---|---|
| 1 | Login, Home and setup checklist |
| 2–4 | Institution, users, roles, academic calendar and structure |
| 5–6 | Students, guardians and admissions |
| 7 | Fees, invoicing, GL posting and payments |
| 8 | Exam eligibility, scheduling, hall tickets, seats, grades and results |
| 9–10 | Facilities, transport, appointments, placements, scholarships |
| 11 | Operational analytics and reports |
| 12 | Notices, notifications and safe Edicai AI use |
| 13 | Public website and Apps review gates |

## 14.7 Daily close-out

- Save and re-open critical records to confirm values survived the reload.
- Verify linked list, parent and child state; do not trust only the form title.
- Leave unpublished notices inactive.
- Record the change ticket number and operator name in structured docs.
- Hand over unresolved access/data issues with the steps already attempted.

> The guide is complete only after all chapters have been read and the Act I/II checklists have been signed off in UAT. A clean production go-live still requires approved data, access review, backups and user acceptance testing.
