# EDICAI Custom Addons — Module Inventory

67 modules · 225 data models · 74 inherited extensions

Legend: 🏠 = application (visible as an app in the menu)

## Core Education Platform (edicai_*) — 58 modules

### `edicai_academic` — Edicai Academic Structure 🏠
*19.0.1.0.0* — Faculty, Department, Program and Specialisation management

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (5) · `security/` (1) · `tests/` (3) · `views/` (7)
**Depends:** edicai_base, edicai_campus, edicai_security, edicai_academic_generic, edicai_institution_profile
**Models (4):** `edicai.department`, `edicai.faculty`, `edicai.program`, `edicai.specialisation`

### `edicai_academic_generic` — Edicai Generic Academic Structure
*19.0.1.0.0* — Generic self-referencing academic unit tree (Faculty, Department, Grade Level, Wing...)

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (3) · `security/` (1) · `tests/` (2) · `views/` (2)
**Depends:** edicai_base, edicai_security
**Models (2):** `edicai.academic.unit`, `edicai.academic.unit.type`

### `edicai_admission` — Admission Management 🏠
*19.0.1.2.0* — Complete admission lifecycle from inquiry to confirmed enrollment

**Sub-packages:** `data/` (6) · `menus/` (3) · `migrations/` (1) · `models/` (20) · `reports/` (1) · `security/` (5) · `static (js/xml/css/scss)/` (1) · `tests/` (10) · `views/` (25) · `wizards/` (2)
**Depends:** mail, edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_security, edicai_student, edicai_curriculum, edicai_faculty_profile, edicai_guardian, edicai_timetable
**Models (15):** `edicai.admission.applicant`, `edicai.admission.cycle`, `edicai.admission.cycle.seat`, `edicai.admission.enrollment`, `edicai.admission.stage`, `edicai.admission.ai.tools`, `edicai.admission.automation.engine`, `edicai.admission.automation.rule`, `edicai.sequence.mixin`, `edicai.enrollment`, `edicai.enrollment.log`, `edicai.enrollment.waitlist`, `edicai.admission.entrance.test`, `edicai.admission.entrance.test.line`, `edicai.admission.offer.letter`
**Extends:** `edicai.admission.applicant`, `edicai.admission.entrance.test`, `edicai.admission.entrance.test.line`, `edicai.admission.offer.letter`, `edicai.course.offering`, `edicai.student`, `res.company`

### `edicai_admission_fees` — Admission Fees Bridge
*19.0.1.0.0* — Bridge between admission and fee management

**Sub-packages:** `models/` (3) · `tests/` (2) · `views/` (2)
**Depends:** edicai_admission, edicai_fees
**Extends:** `edicai.admission.applicant`, `edicai.fee.invoice`

### `edicai_ai` — Edicai AI 🏠
*19.0.2.0.0* — AI-Powered Assistant for Edicai — Powered by OpenCode Zen

**Sub-packages:** `controllers/` (2) · `data/` (1) · `doc/` (0) · `models/` (30) · `security/` (4) · `static (js/xml/css/scss)/` (7) · `tests/` (52) · `views/` (7) · `wizard/` (3)
**Depends:** base, base_setup, mail, portal, edicai_base
**Models (29):** `edicai.ai.action.orchestrator`, `edicai.ai.action.policy`, `edicai.ai.action.resolve`, `edicai.ai.pending.approval`, `edicai.ai.ask.data`, `edicai.ai.audit.event`, `edicai.ai.config`, `edicai.ai.conversation.context`, `edicai.ai.entity.policy`, `edicai.ai.entity.action`, `edicai.ai.entity.tools`, `edicai.ai.intent`, `edicai.ai.orchestrator`, `edicai.ai.pending.action`, `edicai.ai.policy.gate`, `edicai.ai.proactive.insight`, `edicai.ai.proactive`, `edicai.ai.qa.toolkit`, `edicai.ai.llm.responder`, `edicai.ai.tool.registry`, `edicai.ai.conversational.tools`, `edicai.ai.llm.understanding`, `edicai.ai.pending.workflow`, `edicai.ai.workflow.replay`, `edicai.ai.chat.session`, `edicai.ai.chat.message`, `edicai.ai.prompt`, `edicai.ai.provider`, `edicai.ai.usage.log`
**Extends:** `res.config.settings`

### `edicai_alumni` — Alumni Engagement
*19.0.1.0.0* — Bridge Edicai alumni into Odoo mass mailing and events

**Sub-packages:** `data/` (1) · `models/` (4) · `security/` (1) · `static (js/xml/css/scss)/` (0) · `tests/` (2) · `views/` (3)
**Depends:** mass_mailing, event, edicai_student, edicai_base
**Extends:** `edicai.student`, `event.event`, `mailing.list`

### `edicai_analytics` — Analytics 🏠
*19.0.1.0.0* — Institutional analytics dashboards for academic, financial and student data

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (6) · `security/` (2) · `static (js/xml/css/scss)/` (3) · `tests/` (2) · `views/` (5)
**Depends:** edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_curriculum, edicai_timetable, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_scholarship, edicai_admission, edicai_library, edicai_hostel, edicai_transport, mail
**Models (8):** `edicai.grade.distribution.report`, `edicai.semester.result.report`, `edicai.admission.funnel.report`, `edicai.applicant.category.report`, `edicai.fee.collection.report`, `edicai.payment.method.report`, `edicai.student.enrollment.report`, `edicai.attendance.report`
**Extends:** `edicai.admission.applicant`

### `edicai_api` — Edicai API
*19.0.1.0.0* — RESTful API gateway for Edicai ERP

**Sub-packages:** `controllers/` (6) · `data/` (1) · `menus/` (1) · `models/` (2) · `security/` (3) · `tests/` (2) · `views/` (1)
**Depends:** edicai_base, edicai_security, edicai_student, edicai_academic, edicai_admission, edicai_attendance, edicai_grading, edicai_fees, edicai_notify, edicai_curriculum
**Models (2):** `edicai.api.key`, `edicai.api.key.token.wizard`

### `edicai_appointment` — Edicai Appointment 🏠
*19.0.1.0.0* — Online Appointment Booking

**Sub-packages:** `models/` (2) · `security/` (2) · `tests/` (0) · `views/` (2)
**Depends:** edicai_student, edicai_faculty_profile
**Models (2):** `edicai.appointment.slot`, `edicai.appointment.booking`

### `edicai_asset_request` — Asset Request 🏠
*19.0.1.0.0* — Equipment and facility request and approval workflow

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (3) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `views/` (2)
**Depends:** edicai_campus, edicai_faculty_profile, edicai_security
**Models (2):** `edicai.asset`, `edicai.asset.request`

### `edicai_assignment` — Edicai Assignments 🏠
*19.0.1.0.0* — Course assignments, submissions, rubrics and grading for Edicai ERP

**Sub-packages:** `data/` (2) · `menus/` (1) · `models/` (7) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `views/` (10)
**Depends:** edicai_curriculum, edicai_admission, edicai_faculty_profile, edicai_student, edicai_timetable, edicai_notify
**Models (5):** `edicai.assignment`, `edicai.assignment.rubric`, `edicai.assignment.rubric.criterion`, `edicai.assignment.submission`, `edicai.assignment.submission.criterion`
**Extends:** `edicai.course.offering`, `edicai.notification.template`, `edicai.notification.engine`, `edicai.student`

### `edicai_attendance` — Attendance Management 🏠
*19.0.1.1.0* — Session attendance tracking, policy enforcement and shortage alerts

**Sub-packages:** `controllers/` (2) · `data/` (2) · `menus/` (1) · `models/` (7) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `tests/` (3) · `views/` (13) · `wizards/` (5)
**Depends:** edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_faculty_profile, edicai_guardian, edicai_security, edicai_student, edicai_timetable
**Models (5):** `attendance.ai.copilot`, `edicai.attendance.policy`, `edicai.attendance.record`, `edicai.attendance.session`, `edicai.face.registration`
**Extends:** `edicai.student`

### `edicai_base` — SIS 🏠
*19.0.1.0.0* — Base module for Education Management Suite

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (6) · `security/` (2) · `static (js/xml/css/scss)/` (4) · `views/` (4)
**Depends:** base, mail
**Models (4):** `edicai.campus`, `edicai.mixin`, `edicai.overview.dashboard`, `edicai.upload.validator`
**Extends:** `res.company`

### `edicai_calendar` — Edicai Academic Calendar
*19.0.1.0.0* — Academic year, semester, term and holiday management

**Sub-packages:** `menus/` (1) · `models/` (5) · `security/` (1) · `tests/` (3) · `views/` (8) · `wizards/` (3)
**Depends:** edicai_academic, edicai_base, edicai_campus, edicai_security
**Models (4):** `edicai.academic.week`, `edicai.academic.year`, `edicai.holiday`, `edicai.semester`

### `edicai_campus` — Edicai Campus Management
*19.0.1.0.0* — Complete campus, building, room and facility management

**Sub-packages:** `data/` (2) · `menus/` (1) · `models/` (6) · `report/` (1) · `security/` (1) · `views/` (8)
**Depends:** edicai_base, edicai_security
**Models (4):** `edicai.building`, `edicai.facility`, `edicai.floor`, `edicai.room`
**Extends:** `edicai.campus`

### `edicai_convocation` — Convocation Management
*19.0.1.0.0* — Bridge Edicai convocation into Odoo events

**Sub-packages:** `data/` (1) · `models/` (3) · `security/` (1) · `static (js/xml/css/scss)/` (0) · `tests/` (3) · `views/` (2)
**Depends:** event, edicai_student, edicai_base
**Extends:** `event.event`, `edicai.student`

### `edicai_crm` — Admissions CRM
*19.0.1.0.0* — Bridge Edicai admission applicants into Odoo CRM pipeline

**Sub-packages:** `data/` (2) · `models/` (3) · `security/` (1) · `static (js/xml/css/scss)/` (0) · `tests/` (2) · `views/` (2)
**Depends:** crm, edicai_admission, edicai_base
**Extends:** `edicai.admission.applicant`, `crm.stage`, `crm.lead`

### `edicai_curriculum` — Edicai Curriculum 🏠
*19.0.1.0.0* — Program and Curriculum Management for Edicai ERP

**Sub-packages:** `data/` (2) · `menus/` (1) · `models/` (6) · `security/` (3) · `tests/` (3) · `views/` (8)
**Depends:** base, edicai_academic, edicai_base, edicai_campus, edicai_faculty_profile, edicai_security
**Models (5):** `edicai.course`, `edicai.course.offering`, `edicai.course.prerequisite`, `edicai.curriculum`, `edicai.curriculum.line`

### `edicai_demo` — Edicai Demo Data
*19.0.1.0.0* — Realistic demo data for Edicai ERP — institution-aware datasets

**Sub-packages:** `data/` (1) · `demo/` (23) · `models/` (7) · `security/` (1) · `tests/` (3) · `views/` (1)
**Depends:** edicai_institution_profile, edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_curriculum, edicai_timetable, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_scholarship, edicai_admission, edicai_documents, edicai_hostel, edicai_library, edicai_transport, edicai_notify, edicai_assignment, edicai_api, edicai_analytics
**Models (5):** `edicai.demo.setup`, `edicai.demo.generator`, `edicai.demo.profile`, `edicai.demo.record`, `edicai.demo.generate.wizard`

### `edicai_digital_library` — Edicai Digital Library 🏠
*19.0.1.0.0* — Digital Library Materials

**Sub-packages:** `models/` (2) · `security/` (2) · `tests/` (0) · `views/` (2)
**Depends:** edicai_student, edicai_library
**Models (1):** `edicai.digital.material`

### `edicai_discipline` — Edicai Discipline 🏠
*19.0.1.0.0* — Discipline Management

**Sub-packages:** `models/` (2) · `security/` (2) · `tests/` (0) · `views/` (2)
**Depends:** edicai_student, edicai_faculty_profile
**Models (2):** `edicai.misbehaviour.category`, `edicai.discipline.record`

### `edicai_documents` — Documents 🏠
*19.0.1.0.1* — Centralised document management for students, faculty and institution

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (6) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `views/` (7)
**Depends:** mail, edicai_academic, edicai_admission, edicai_base, edicai_calendar, edicai_campus, edicai_faculty_profile, edicai_security, edicai_student
**Models (3):** `edicai.document`, `edicai.document.category`, `edicai.document.template`
**Extends:** `edicai.faculty.member`, `edicai.student`

### `edicai_exam` — Examination Management 🏠
*19.0.1.0.0* — Exam scheduling, hall tickets, seating plans and eligibility checks

**Sub-packages:** `data/` (2) · `menus/` (1) · `models/` (4) · `reports/` (2) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `tests/` (2) · `views/` (11) · `wizards/` (2)
**Depends:** edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_faculty_profile, edicai_guardian, edicai_security, edicai_student, edicai_timetable
**Models (3):** `edicai.exam.hall.ticket`, `edicai.exam.schedule`, `edicai.exam.seating`

### `edicai_faculty_profile` — Edicai Faculty & Staff 🏠
*19.0.1.0.0* — Faculty member and administrative staff profile management

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (6) · `security/` (2) · `views/` (8)
**Depends:** edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_security, edicai_student
**Models (5):** `edicai.faculty.member`, `edicai.faculty.publication`, `edicai.faculty.qualification`, `edicai.faculty.workload`, `edicai.staff.member`

### `edicai_fees` — Fees 🏠
*19.0.1.2.0* — Student fee management, invoicing and payment tracking

**Sub-packages:** `data/` (5) · `menus/` (1) · `models/` (12) · `reports/` (3) · `security/` (3) · `static (js/xml/css/scss)/` (0) · `tests/` (4) · `views/` (15)
**Depends:** account, mail, edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_grading, edicai_guardian, edicai_security, edicai_student, edicai_timetable
**Models (8):** `edicai.fee.copilot`, `edicai.fee.accounting.config`, `edicai.fee.invoice`, `edicai.fee.invoice.line`, `edicai.fee.invoice.batch.wizard`, `edicai.fee.payment`, `edicai.fee.structure`, `edicai.fee.structure.line`
**Extends:** `account.partial.reconcile`, `edicai.fee.invoice`, `edicai.student`

### `edicai_finance_report` — Finance Reports 🏠
*19.0.1.0.0* — Financial dashboards, fee analytics and revenue reporting

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (3) · `report/` (2) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `views/` (6)
**Depends:** mail, edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_fees, edicai_grading, edicai_guardian, edicai_scholarship, edicai_security, edicai_student, edicai_timetable
**Models (2):** `edicai.finance.kpi`, `edicai.finance.snapshot`

### `edicai_gradebook` — Edicai Grade Book 🏠
*19.0.1.1.0* — Per-course assignment grade book with CA weighting, integrated with Grading & Results

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (6) · `reports/` (2) · `security/` (2) · `tests/` (3) · `views/` (5)
**Depends:** edicai_assignment, edicai_grading
**Models (3):** `edicai.gradebook.assignment.line`, `edicai.gradebook.config`, `edicai.gradebook.student.line`
**Extends:** `edicai.assignment.submission`, `edicai.course.offering`

### `edicai_grading` — Grading & Results 🏠
*19.0.1.1.0* — Marks entry, grade computation, GPA/CGPA and semester results

**Sub-packages:** `data/` (4) · `menus/` (1) · `models/` (6) · `reports/` (3) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `tests/` (4) · `views/` (13)
**Depends:** edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_guardian, edicai_security, edicai_student, edicai_timetable
**Models (5):** `grading.ai.copilot`, `edicai.grade.entry`, `edicai.grade.scale`, `edicai.grade.scale.line`, `edicai.semester.result`
**Extends:** `edicai.enrollment`, `edicai.student`

### `edicai_grievance` — Edicai Grievance 🏠
*19.0.1.0.0* — Grievance Management

**Sub-packages:** `controllers/` (2) · `data/` (2) · `models/` (3) · `security/` (2) · `tests/` (0) · `views/` (3)
**Depends:** edicai_student, edicai_faculty_profile, edicai_guardian, edicai_notify, edicai_portal_student, edicai_portal_guardian
**Models (4):** `grievance.ai.copilot`, `edicai.grievance.category`, `edicai.grievance.team`, `edicai.grievance.request`

### `edicai_guardian` — Edicai Guardians 🏠
*19.0.1.0.0* — Parent and guardian profile management with portal access

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (4) · `security/` (2) · `views/` (3)
**Depends:** edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile
**Models (2):** `edicai.guardian`, `edicai.guardian.student.rel`
**Extends:** `edicai.student`

### `edicai_hostel` — Hostel 🏠
*19.0.1.0.0* — University hostel and accommodation management for student residences

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (5) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `views/` (11)
**Depends:** mail, edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_security, edicai_student
**Models (4):** `edicai.hostel.allocation`, `edicai.hostel.block`, `edicai.hostel.maintenance`, `edicai.hostel.room`

### `edicai_institution_profile` — Edicai Institution Profile
*19.0.1.3.0* — Institution type, terminology and feature profiles driving multi-entity behavior

**Sub-packages:** `data/` (2) · `menus/` (1) · `migrations/` (1) · `models/` (11) · `security/` (1) · `tests/` (8) · `views/` (5)
**Depends:** edicai_base, edicai_security, edicai_academic_generic
**Models (4):** `edicai.grading.scheme`, `edicai.institution.feature`, `edicai.institution.profile`, `edicai.terminology.profile`
**Extends:** `base`, `edicai.academic.unit`, `ir.actions.act_window`, `ir.ui.menu`, `ir.ui.view`, `res.company`

### `edicai_library` — Library 🏠
*19.0.1.0.0* — University library management with catalogue, issue tracking and fines

**Sub-packages:** `data/` (2) · `menus/` (1) · `models/` (6) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `tests/` (2) · `views/` (11)
**Depends:** mail, edicai_academic, edicai_base, edicai_campus, edicai_faculty_profile, edicai_security, edicai_student
**Models (9):** `library.ai.copilot`, `edicai.library.subject`, `edicai.library.publisher`, `edicai.library.book`, `edicai.library.author`, `edicai.library.book.copy`, `edicai.library.issue`, `edicai.library.member`, `edicai.library.reservation`

### `edicai_lms` — Edicai LMS 🏠
*1.0* — Advanced Learning Management System for Edicai

**Sub-packages:** `controllers/` (2) · `demo/` (1) · `models/` (4) · `security/` (1) · `views/` (6)
**Depends:** base, website_slides, website_sale_slides, edicai_academic, edicai_student, edicai_assignment, edicai_quiz, edicai_gradebook
**Extends:** `slide.channel`, `slide.slide`

### `edicai_mentor` — Edicai Student Mentor 🏠
*19.0.1.0.0* — Student Mentoring System

**Sub-packages:** `models/` (2) · `security/` (2) · `tests/` (0) · `views/` (2)
**Depends:** edicai_student, edicai_faculty_profile
**Models (2):** `edicai.mentor.allocation`, `edicai.mentor.meeting.log`

### `edicai_notice_board` — Edicai Notice Board 🏠
*19.0.1.0.0* — Persistent circulars and notices for students, faculty and guardians

**Sub-packages:** `menus/` (1) · `models/` (2) · `security/` (1) · `views/` (2)
**Depends:** mail, edicai_base, edicai_security, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_academic
**Models (1):** `edicai.notice`

### `edicai_notify` — Notifications 🏠
*19.0.1.0.0* — Multi-channel notification engine for email, WhatsApp and in-app alerts

**Sub-packages:** `controllers/` (2) · `data/` (5) · `menus/` (1) · `models/` (7) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `views/` (6)
**Depends:** mail, edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_fees, edicai_grading, edicai_guardian, edicai_scholarship, edicai_security, edicai_student, edicai_timetable
**Models (6):** `edicai.notification.automation`, `edicai.notification.config`, `edicai.notification.engine`, `edicai.notification.log`, `edicai.notification.template`, `edicai.whatsapp.flows`

### `edicai_payment` — Online Fee Payments
*19.0.1.0.0* — Online fee payment for Edicai through Odoo payment providers

**Sub-packages:** `models/` (3) · `security/` (1) · `static (js/xml/css/scss)/` (0) · `tests/` (2) · `views/` (2)
**Depends:** account_payment, payment, edicai_fees, edicai_portal_student
**Extends:** `edicai.fee.invoice`, `payment.transaction`

### `edicai_placement` — Edicai Placement 🏠
*19.0.1.0.0* — Placement Management

**Sub-packages:** `models/` (2) · `security/` (2) · `tests/` (0) · `views/` (2)
**Depends:** edicai_student
**Models (3):** `edicai.placement.company`, `edicai.placement.drive`, `edicai.placement.application`

### `edicai_portal_faculty` — Edicai Faculty Portal 🏠
*19.0.1.0.0* — Faculty self-service portal for schedule, attendance and grade entry

**Sub-packages:** `controllers/` (3) · `security/` (1) · `views/` (2)
**Depends:** edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_curriculum, edicai_timetable, edicai_admission, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_scholarship, edicai_notify, edicai_assignment, edicai_portal_student, edicai_notice_board, portal

### `edicai_portal_guardian` — Edicai Guardian Portal 🏠
*19.0.1.0.0* — Guardian self-service portal for ward academic and fee monitoring

**Sub-packages:** `controllers/` (3) · `security/` (1) · `views/` (1)
**Depends:** edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_guardian, edicai_curriculum, edicai_admission, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_notify, edicai_portal_student, edicai_notice_board, portal

### `edicai_portal_student` — Edicai Student Portal 🏠
*19.0.1.0.0* — Student self-service portal for academic records, fees and results

**Sub-packages:** `controllers/` (3) · `models/` (2) · `security/` (1) · `static (js/xml/css/scss)/` (1) · `views/` (3)
**Depends:** edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_curriculum, edicai_timetable, edicai_admission, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_scholarship, edicai_notify, edicai_assignment, edicai_notice_board, portal
**Extends:** `edicai.student`

### `edicai_progression` — Edicai Progression 🏠
*19.0.1.0.0* — Student Progression Management

**Sub-packages:** `models/` (2) · `security/` (2) · `tests/` (2) · `views/` (2)
**Depends:** edicai_student, edicai_grading, edicai_attendance, edicai_curriculum
**Models (1):** `edicai.progression.record`

### `edicai_quiz` — Edicai Quiz 🏠
*19.0.1.0.0* — Quiz / Question Bank + Anti-Cheating

**Sub-packages:** `controllers/` (0) · `models/` (2) · `security/` (2) · `static (js/xml/css/scss)/` (2) · `tests/` (0) · `views/` (2)
**Depends:** edicai_student
**Models (3):** `edicai.question.bank`, `edicai.quiz`, `edicai.quiz.attempt`

### `edicai_scholarship` — Scholarships 🏠
*19.0.1.0.0* — Scholarship programs, applications and financial aid disbursement

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (5) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `tests/` (2) · `views/` (11)
**Depends:** mail, edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_fees, edicai_grading, edicai_guardian, edicai_security, edicai_student, edicai_timetable
**Models (3):** `edicai.scholarship.application`, `edicai.scholarship.award`, `edicai.scholarship.program`
**Extends:** `edicai.student`

### `edicai_secure_transcript` — Edicai Secure Transcript 🏠
*19.0.1.0.0* — Secure Transcript with QR Verification

**Sub-packages:** `controllers/` (2) · `models/` (2) · `security/` (2) · `tests/` (0) · `views/` (2)
**Depends:** edicai_student, edicai_grading, website
**Models (1):** `edicai.secure.transcript`

### `edicai_security` — Edicai Security
*19.0.1.0.0* — Security and access control for Edicai Education Management Suite

**Sub-packages:** `models/` (2) · `security/` (0) · `tests/` (2)
**Depends:** edicai_base
**Extends:** `res.users`

### `edicai_skill_assessment` — Edicai Student Skill Assessment 🏠
*19.0.1.0.0* — Student Skill Assessment System

**Sub-packages:** `models/` (2) · `security/` (2) · `tests/` (0) · `views/` (2)
**Depends:** edicai_student, edicai_faculty_profile
**Models (2):** `edicai.skill`, `edicai.student.skill.assessment`

### `edicai_student` — Edicai Students 🏠
*19.0.1.0.0* — Complete student profile and lifecycle management

**Sub-packages:** `data/` (4) · `menus/` (1) · `models/` (5) · `reports/` (3) · `security/` (2) · `tests/` (4) · `views/` (6) · `wizards/` (5)
**Depends:** edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_academic_generic, edicai_calendar
**Models (4):** `edicai.student`, `edicai.student.academic.history`, `edicai.student.document`, `edicai.student.emergency.contact`

### `edicai_student_leave` — Edicai Student Leave Requests 🏠
*19.0.1.0.0* — Student/guardian-initiated leave request workflow with approval routing

**Sub-packages:** `controllers/` (2) · `data/` (2) · `menus/` (1) · `models/` (3) · `security/` (2) · `views/` (2)
**Depends:** edicai_student, edicai_guardian, edicai_notify, edicai_portal_student, edicai_portal_guardian
**Models (1):** `edicai.student.leave.request`
**Extends:** `edicai.notification.template`

### `edicai_studio` — Forge Studio — AI No-Code Platform (Odoo Studio UX Parity) 🏠
*19.0.2.0.0* — Odoo Studio UX Parity: 3-pane shell, Selection Manager, Properties, Drag-Drop, AI Copilot

**Sub-packages:** `controllers/` (4) · `data/` (4) · `menus/` (1) · `models/` (19) · `security/` (3) · `static (js/xml/css/scss)/` (26) · `views/` (18) · `wizards/` (5)
**Depends:** base, mail, web, edicai_base, edicai_security
**Models (30):** `studio.ai.copilot`, `studio.ai.request`, `studio.ai.operation`, `studio.app`, `studio.automation`, `studio.automation.log`, `studio.dashboard`, `studio.dashboard.widget`, `studio.data.dictionary`, `studio.dataset`, `studio.dsl`, `studio.expression`, `studio.field`, `studio.health`, `studio.model`, `studio.record`, `studio.record.value`, `studio.report`, `studio.report.template`, `studio.security.group`, `studio.security.rule`, `studio.field.permission`, `studio.version`, `studio.dependency`, `studio.view`, `studio.workflow`, `studio.workflow.node`, `studio.workflow.transition`, `studio.workflow.instance`, `studio.workflow.log`

### `edicai_theme` — Edicai Premium Theme 🏠
*19.0.1.0.0* — Enterprise-style premium backend theme for Edicai ERP

**Sub-packages:** `data/` (1) · `static (js/xml/css/scss)/` (20) · `views/` (1)
**Depends:** web, mail, edicai_base

### `edicai_thesis` — Edicai Thesis 🏠
*19.0.1.0.0* — Thesis Management

**Sub-packages:** `models/` (2) · `security/` (2) · `tests/` (0) · `views/` (2)
**Depends:** edicai_student, edicai_faculty_profile
**Models (2):** `edicai.thesis`, `edicai.thesis.review`

### `edicai_timetable` — Timetable & Scheduling 🏠
*19.0.1.0.0* — Class scheduling, time slots and conflict-free timetable generation

**Sub-packages:** `data/` (2) · `menus/` (1) · `models/` (5) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `tests/` (2) · `views/` (8) · `wizards/` (3)
**Depends:** edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_faculty_profile, edicai_guardian, edicai_security, edicai_student
**Models (4):** `timetable.ai.copilot`, `edicai.room.booking`, `edicai.time.slot`, `edicai.timetable.entry`

### `edicai_transport` — Transport 🏠
*19.0.1.0.0* — University student transport management with routes and passes

**Sub-packages:** `data/` (1) · `menus/` (1) · `models/` (5) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `views/` (9)
**Depends:** mail, edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_security, edicai_student
**Models (5):** `edicai.transport.pass`, `edicai.transport.route`, `edicai.transport.stop`, `edicai.transport.trip`, `edicai.transport.vehicle`

### `edicai_transport_fleet` — Transport Fleet Integration
*19.0.1.0.0* — Bridge Edicai transport vehicles into Odoo Fleet management

**Sub-packages:** `data/` (1) · `models/` (3) · `security/` (1) · `static (js/xml/css/scss)/` (0) · `tests/` (2) · `views/` (1)
**Depends:** fleet, edicai_transport, edicai_base
**Extends:** `fleet.vehicle`, `edicai.transport.vehicle`

### `edicai_web_theme` — Edicai Web Theme
*19.0.1.0.0* — Light/dark color scheme with a General Settings toggle (modern SaaS UI base)

**Sub-packages:** `controllers/` (2) · `models/` (2) · `static (js/xml/css/scss)/` (2) · `tests/` (2) · `views/` (1)
**Depends:** web
**Extends:** `res.config.settings`

### `edicai_website` — Admissions Website
*19.0.1.0.0* — Bridge Edicai admissions into Odoo website, livechat and CRM

**Sub-packages:** `controllers/` (3) · `data/` (3) · `models/` (4) · `security/` (1) · `static (js/xml/css/scss)/` (0) · `tests/` (3) · `views/` (5)
**Depends:** website, im_livechat, crm, edicai_admission, edicai_base
**Extends:** `crm.lead`, `im_livechat.channel`, `website`

## Backend UI Extensions (muk_*) — 7 modules

### `muk_web_appsbar` — MuK AppsBar
*19.0.1.1.12* — Adds a sidebar to the main screen

**Sub-packages:** `doc/` (0) · `i18n/` (0) · `models/` (5) · `static (js/xml/css/scss)/` (13) · `templates/` (1) · `tests/` (5) · `views/` (2)
**Depends:** base_setup, web
**Extends:** `ir.http`, `res.company`, `res.config.settings`, `res.users`

### `muk_web_chatter` — MuK Chatter
*19.0.1.4.10* — Adds options for the chatter

**Sub-packages:** `doc/` (0) · `i18n/` (0) · `models/` (4) · `static (js/xml/css/scss)/` (21) · `tests/` (5) · `views/` (1)
**Depends:** mail
**Extends:** `ir.http`, `mail.thread`, `res.users`

### `muk_web_colors` — MuK Colors
*19.0.1.0.9* — Customize your Odoo colors

**Sub-packages:** `doc/` (0) · `i18n/` (0) · `models/` (3) · `static (js/xml/css/scss)/` (3) · `templates/` (1) · `tests/` (3) · `views/` (1)
**Depends:** web, base_setup
**Models (1):** `muk_web_colors.color_assets_editor`
**Extends:** `res.config.settings`

### `muk_web_dialog` — MuK Dialog
*19.0.1.0.11* — Adds options for the dialogs

**Sub-packages:** `doc/` (0) · `i18n/` (0) · `models/` (3) · `static (js/xml/css/scss)/` (7) · `tests/` (4) · `views/` (1)
**Depends:** web
**Extends:** `ir.http`, `res.users`

### `muk_web_group` — MuK Groups
*19.0.1.0.7* — Adds expand/collapse for views

**Sub-packages:** `doc/` (0) · `i18n/` (0) · `static (js/xml/css/scss)/` (7) · `tests/` (2)
**Depends:** web

### `muk_web_refresh` — MuK Web Refresh
*19.0.1.1.12* — Refresh views manually, automatically, or from the backend

**Sub-packages:** `demo/` (2) · `doc/` (0) · `i18n/` (0) · `models/` (3) · `static (js/xml/css/scss)/` (8) · `tests/` (4) · `views/` (1)
**Depends:** web, bus, base_automation
**Extends:** `ir.actions.server`, `ir.http`

### `muk_web_theme` — MuK Backend Theme
*19.0.1.4.9* — Odoo Community Backend Theme

**Sub-packages:** `doc/` (0) · `i18n/` (0) · `models/` (4) · `static (js/xml/css/scss)/` (15) · `templates/` (1) · `tests/` (4) · `views/` (1)
**Depends:** muk_web_group, muk_web_chatter, muk_web_dialog, muk_web_appsbar, muk_web_colors, muk_web_refresh
**Extends:** `ir.http`, `res.company`, `res.config.settings`

## Integrations — 2 modules

### `odoo_modern_backend_full` — Odoo Modern SaaS Backend UX 🏠
*19.0.2.1.0* — Modern SaaS shell, OWL components, dashboards, dynamic sidebar and live theme customization for Odoo Community

**Sub-packages:** `static (js/xml/css/scss)/` (16) · `tests/` (2) · `views/` (1)
**Depends:** web

### `telegram_odoo_integration` — Telegram Odoo Integration
*19.0.2.0.0* — Collect orders via Telegram and submit to AI Parser for Sales Order creation

**Sub-packages:** `controllers/` (2) · `data/` (1) · `models/` (16) · `security/` (2) · `static (js/xml/css/scss)/` (0) · `tests/` (3) · `views/` (4)
**Depends:** base, sale, edicai_student, edicai_guardian
**Models (5):** `telegram.chat.link`, `telegram.message`, `telegram.order.session`, `telegram.session.message`, `telegram.session.attachment`
**Extends:** `res.config.settings`, `res.partner`, `sale.order`
