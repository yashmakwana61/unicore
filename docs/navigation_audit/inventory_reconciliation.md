# Inventory Reconciliation

Claimed: 31 top-level apps, 266 menu entries.

| Measure | Actual (live DB) |
|---|---|
| Total `ir_ui.menu` records | **695** |
| Top-level roots (all) | **48** |
| Custom-owned top-level roots (edicai_, muk_, telegram_, odoo_modern_*) | **31** |
| Custom-owned menus (all depths) | **268** |
| Standard Odoo menus owned by core modules | 427 |
| Inactive/hidden menus | 4 |
| Menus without any external ID | 0 |
| User-facing classified | 584 |
| Technical classified (Settings subtree / no_one) | 63 |

### Verdict

The claimed figures are **within scope but under the surface**: 31 custom root apps exist (claimed 31) and 268 custom-owned menus exist (claimed 266). The full database contains 695 menus in total — the remainder (427) are standard Odoo menus (Settings, Discuss, Website, mail templates, etc.) that also appear in navigation and MUST be accounted for when restructuring.

### Top-level roots (custom)

- Admission — `edicai_admission.menu_edicai_admission_root` — direct children: 8
- Advanced LMS — `edicai_lms.menu_edicai_lms_root` — direct children: 4
- Analytics — `edicai_analytics.menu_edicai_analytics_root` — direct children: 4
- Appointments — `edicai_appointment.menu_edicai_appointment_root` — direct children: 2
- Asset Requests — `edicai_asset_request.menu_edicai_asset_request_root` — direct children: 2
- Assignments — `edicai_assignment.menu_edicai_assignment` — direct children: 6
- Attendance — `edicai_attendance.menu_edicai_attendance` — direct children: 9
- Digital Library — `edicai_digital_library.menu_edicai_digital_library_root` — direct children: 1
- Discipline — `edicai_discipline.menu_edicai_discipline_root` — direct children: 2
- Documents — `edicai_documents.menu_edicai_documents_root` — direct children: 6
- Edicai — `edicai_base.menu_edicai_root` — direct children: 9
- Edicai AI — `edicai_ai.menu_edicai_ai_root` — direct children: 4
- Examinations — `edicai_exam.menu_edicai_exam` — direct children: 8
- Fees — `edicai_fees.menu_edicai_fees_root` — direct children: 3
- Finance Reports — `edicai_finance_report.menu_edicai_finance_report_root` — direct children: 4
- Grading — `edicai_grading.menu_edicai_grading` — direct children: 8
- Grievances — `edicai_grievance.menu_edicai_grievance_root` — direct children: 2
- Hostel — `edicai_hostel.menu_edicai_hostel_root` — direct children: 4
- Library — `edicai_library.menu_edicai_library_root` — direct children: 5
- Mentoring — `edicai_mentor.menu_edicai_mentor_root` — direct children: 2
- Notice Board — `edicai_notice_board.menu_edicai_notice_root` — direct children: 1
- Notifications — `edicai_notify.menu_edicai_notify_root` — direct children: 2
- Placements — `edicai_placement.menu_edicai_placement_root` — direct children: 3
- Progression — `edicai_progression.menu_edicai_progression_root` — direct children: 1
- Quizzes — `edicai_quiz.menu_edicai_quiz_root` — direct children: 4
- Scholarships — `edicai_scholarship.menu_edicai_scholarship_root` — direct children: 4
- Secure Transcripts — `edicai_secure_transcript.menu_edicai_secure_transcript_root` — direct children: 1
- Skill Assessment — `edicai_skill_assessment.menu_edicai_skill_root` — direct children: 2
- Thesis Management — `edicai_thesis.menu_edicai_thesis_root` — direct children: 2
- Timetable — `edicai_timetable.menu_edicai_timetable` — direct children: 5
- Transport — `edicai_transport.menu_edicai_transport_root` — direct children: 4

### Top-level roots (standard Odoo)

- Apps — `base.menu_management`
- Calendar — `calendar.mail_menu_calendar`
- Contacts — `contacts.menu_contacts`
- CRM — `crm.crm_menu_root`
- Dashboards — `spreadsheet_dashboard.spreadsheet_dashboard_menu_root`
- Discuss — `mail.menu_root_discuss`
- eLearning — `website_slides.website_slides_menu_root`
- Email Marketing — `mass_mailing.mass_mailing_menu_root`
- Events — `event.event_main_menu`
- Fleet — `fleet.menu_root`
- Invoicing — `account.menu_finance`
- Link Tracker — `utm.menu_link_tracker_root`
- Live Chat — `im_livechat.menu_livechat_root`
- Sales — `sale.sale_menu_root`
- Settings — `base.menu_administration`
- Tests — `base.menu_tests`
- Website — `website.menu_website_configuration`