# Module Dependency & Ownership Map

Source: live DB (ir.ui.menu / res.groups) + manifest AST parse. Generated from database `edicai` (local staging).

## `edicai_academic`
- Manifest name: Edicai Academic Structure (19.0.1.0.0) — App: yes
- Depends: edicai_base, edicai_campus, edicai_security, edicai_academic_generic, edicai_institution_profile
- Menus owned in DB: 5
- Actions used by menus (owned): 4
- Security groups defined: —
- Data models (4): `edicai.program`, `edicai.department`, `edicai.specialisation`, `edicai.faculty`

## `edicai_academic_generic`
- Manifest name: Edicai Generic Academic Structure (19.0.1.0.0) — App: no
- Depends: edicai_base, edicai_security
- Menus owned in DB: 2
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (2): `edicai.academic.unit`, `edicai.academic.unit.type`

## `edicai_admission`
- Manifest name: Admission Management (19.0.1.2.0) — App: yes
- Depends: mail, edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_security, edicai_student, edicai_curriculum, edicai_faculty_profile, edicai_guardian, edicai_timetable
- Menus owned in DB: 15
- Actions used by menus (owned): 12
- Security groups defined: —
- Data models (15): `edicai.admission.applicant`, `edicai.admission.offer.letter`, `edicai.admission.automation.engine`, `edicai.admission.stage`, `edicai.enrollment.log`, `edicai.enrollment.waitlist`, `edicai.admission.entrance.test`, `edicai.admission.entrance.test.line`, `edicai.admission.enrollment`, `edicai.admission.ai.tools`, `edicai.admission.cycle`, `edicai.admission.cycle.seat`, `edicai.admission.automation.rule`, `edicai.enrollment`, `edicai.sequence.mixin`
- Extends (7): `res.company`, `edicai.student`, `edicai.admission.applicant`, `edicai.course.offering`, `edicai.admission.offer.letter`, `edicai.admission.entrance.test`, `edicai.admission.entrance.test.line`

## `edicai_admission_fees`
- Manifest name: Admission Fees Bridge (19.0.1.0.0) — App: no
- Depends: edicai_admission, edicai_fees
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (2): `edicai.admission.applicant`, `edicai.fee.invoice`

## `edicai_ai`
- Manifest name: Edicai AI (19.0.2.0.0) — App: yes
- Depends: base, base_setup, mail, portal, edicai_base
- Menus owned in DB: 7
- Actions used by menus (owned): 3
- Security groups defined: `group_edicai_ai_user` (AI User); `group_edicai_ai_manager` (AI Manager) [implies base.group_system]
- Data models (29): `edicai.ai.prompt`, `edicai.ai.action.orchestrator`, `edicai.ai.intent`, `edicai.ai.policy.gate`, `edicai.ai.action.resolve`, `edicai.ai.proactive.insight`, `edicai.ai.proactive`, `edicai.ai.entity.tools`, `edicai.ai.qa.toolkit`, `edicai.ai.pending.approval`, `edicai.ai.action.policy`, `edicai.ai.llm.understanding`, `edicai.ai.usage.log`, `edicai.ai.orchestrator`, `edicai.ai.chat.session`, `edicai.ai.chat.message`, `edicai.ai.conversational.tools`, `edicai.ai.entity.policy`, `edicai.ai.entity.action`, `edicai.ai.conversation.context`, `edicai.ai.config`, `edicai.ai.ask.data`, `edicai.ai.llm.responder`, `edicai.ai.provider`, `edicai.ai.pending.workflow`, `edicai.ai.workflow.replay`, `edicai.ai.pending.action`, `edicai.ai.audit.event`, `edicai.ai.tool.registry`
- Extends (1): `res.config.settings`

## `edicai_alumni`
- Manifest name: Alumni Engagement (19.0.1.0.0) — App: no
- Depends: mass_mailing, event, edicai_student, edicai_base
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (3): `event.event`, `edicai.student`, `mailing.list`

## `edicai_analytics`
- Manifest name: Analytics (19.0.1.0.0) — App: yes
- Depends: edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_curriculum, edicai_timetable, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_scholarship, edicai_admission, edicai_library, edicai_hostel, edicai_transport, mail
- Menus owned in DB: 14
- Actions used by menus (owned): 8
- Security groups defined: —
- Data models (8): `edicai.student.enrollment.report`, `edicai.attendance.report`, `edicai.fee.collection.report`, `edicai.payment.method.report`, `edicai.admission.funnel.report`, `edicai.applicant.category.report`, `edicai.grade.distribution.report`, `edicai.semester.result.report`
- Extends (1): `edicai.admission.applicant`

## `edicai_api`
- Manifest name: Edicai API (19.0.1.0.0) — App: no
- Depends: edicai_base, edicai_security, edicai_student, edicai_academic, edicai_admission, edicai_attendance, edicai_grading, edicai_fees, edicai_notify, edicai_curriculum
- Menus owned in DB: 2
- Actions used by menus (owned): 1
- Security groups defined: `group_edicai_api_user` (API User) [implies edicai_api.group_edicai_api_admin]; `group_edicai_api_admin` (API Admin)
- Data models (2): `edicai.api.key`, `edicai.api.key.token.wizard`

## `edicai_appointment`
- Manifest name: Edicai Appointment (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_faculty_profile
- Menus owned in DB: 3
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (2): `edicai.appointment.slot`, `edicai.appointment.booking`

## `edicai_asset_request`
- Manifest name: Asset Request (19.0.1.0.0) — App: yes
- Depends: edicai_campus, edicai_faculty_profile, edicai_security
- Menus owned in DB: 11
- Actions used by menus (owned): 7
- Security groups defined: —
- Data models (2): `edicai.asset`, `edicai.asset.request`

## `edicai_assignment`
- Manifest name: Edicai Assignments (19.0.1.0.0) — App: yes
- Depends: edicai_curriculum, edicai_admission, edicai_faculty_profile, edicai_student, edicai_timetable, edicai_notify
- Menus owned in DB: 7
- Actions used by menus (owned): 6
- Security groups defined: —
- Data models (5): `edicai.assignment.rubric`, `edicai.assignment.rubric.criterion`, `edicai.assignment`, `edicai.assignment.submission`, `edicai.assignment.submission.criterion`
- Extends (4): `edicai.student`, `edicai.notification.template`, `edicai.notification.engine`, `edicai.course.offering`

## `edicai_attendance`
- Manifest name: Attendance Management (19.0.1.1.0) — App: yes
- Depends: edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_faculty_profile, edicai_guardian, edicai_security, edicai_student, edicai_timetable
- Menus owned in DB: 10
- Actions used by menus (owned): 9
- Security groups defined: —
- Data models (5): `edicai.attendance.policy`, `attendance.ai.copilot`, `edicai.attendance.session`, `edicai.face.registration`, `edicai.attendance.record`
- Extends (1): `edicai.student`

## `edicai_base`
- Manifest name: SIS (19.0.1.0.0) — App: yes
- Depends: base, mail
- Menus owned in DB: 4
- Actions used by menus (owned): 1
- Security groups defined: `group_edicai_student` (Student); `group_edicai_faculty` (Faculty) [implies edicai_base.group_edicai_admin]; `group_edicai_staff` (Staff) [implies edicai_base.group_edicai_admin]; `group_edicai_registrar` (Registrar) [implies edicai_base.group_edicai_admin]; `group_edicai_finance` (Finance) [implies edicai_base.group_edicai_admin]; `group_edicai_manager` (Manager) [implies edicai_base.group_edicai_admin]; `group_edicai_admin` (Admin)
- Data models (4): `edicai.campus`, `edicai.overview.dashboard`, `edicai.mixin`, `edicai.upload.validator`
- Extends (1): `res.company`

## `edicai_calendar`
- Manifest name: Edicai Academic Calendar (19.0.1.0.0) — App: no
- Depends: edicai_academic, edicai_base, edicai_campus, edicai_security
- Menus owned in DB: 5
- Actions used by menus (owned): 4
- Security groups defined: —
- Data models (4): `edicai.semester`, `edicai.holiday`, `edicai.academic.week`, `edicai.academic.year`

## `edicai_campus`
- Manifest name: Edicai Campus Management (19.0.1.0.0) — App: no
- Depends: edicai_base, edicai_security
- Menus owned in DB: 4
- Actions used by menus (owned): 4
- Security groups defined: —
- Data models (4): `edicai.facility`, `edicai.room`, `edicai.building`, `edicai.floor`
- Extends (1): `edicai.campus`

## `edicai_convocation`
- Manifest name: Convocation Management (19.0.1.0.0) — App: no
- Depends: event, edicai_student, edicai_base
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (2): `event.event`, `edicai.student`

## `edicai_crm`
- Manifest name: Admissions CRM (19.0.1.0.0) — App: no
- Depends: crm, edicai_admission, edicai_base
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (3): `edicai.admission.applicant`, `crm.stage`, `crm.lead`

## `edicai_curriculum`
- Manifest name: Edicai Curriculum (19.0.1.0.0) — App: yes
- Depends: base, edicai_academic, edicai_base, edicai_campus, edicai_faculty_profile, edicai_security
- Menus owned in DB: 5
- Actions used by menus (owned): 4
- Security groups defined: —
- Data models (5): `edicai.course`, `edicai.curriculum`, `edicai.curriculum.line`, `edicai.course.offering`, `edicai.course.prerequisite`

## `edicai_demo`
- Manifest name: Edicai Demo Data (19.0.1.0.0) — App: no
- Depends: edicai_institution_profile, edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_curriculum, edicai_timetable, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_scholarship, edicai_admission, edicai_documents, edicai_hostel, edicai_library, edicai_transport, edicai_notify, edicai_assignment, edicai_api, edicai_analytics
- Menus owned in DB: 3
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (5): `edicai.demo.record`, `edicai.demo.setup`, `edicai.demo.generator`, `edicai.demo.generate.wizard`, `edicai.demo.profile`

## `edicai_digital_library`
- Manifest name: Edicai Digital Library (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_library
- Menus owned in DB: 2
- Actions used by menus (owned): 1
- Security groups defined: —
- Data models (1): `edicai.digital.material`

## `edicai_discipline`
- Manifest name: Edicai Discipline (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_faculty_profile
- Menus owned in DB: 4
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (2): `edicai.misbehaviour.category`, `edicai.discipline.record`

## `edicai_documents`
- Manifest name: Documents (19.0.1.0.1) — App: yes
- Depends: mail, edicai_academic, edicai_admission, edicai_base, edicai_calendar, edicai_campus, edicai_faculty_profile, edicai_security, edicai_student
- Menus owned in DB: 8
- Actions used by menus (owned): 6
- Security groups defined: —
- Data models (3): `edicai.document.template`, `edicai.document.category`, `edicai.document`
- Extends (2): `edicai.faculty.member`, `edicai.student`

## `edicai_exam`
- Manifest name: Examination Management (19.0.1.0.0) — App: yes
- Depends: edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_faculty_profile, edicai_guardian, edicai_security, edicai_student, edicai_timetable
- Menus owned in DB: 9
- Actions used by menus (owned): 8
- Security groups defined: —
- Data models (3): `edicai.exam.seating`, `edicai.exam.hall.ticket`, `edicai.exam.schedule`

## `edicai_faculty_profile`
- Manifest name: Edicai Faculty & Staff (19.0.1.0.0) — App: yes
- Depends: edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_security, edicai_student
- Menus owned in DB: 6
- Actions used by menus (owned): 5
- Security groups defined: —
- Data models (5): `edicai.staff.member`, `edicai.faculty.member`, `edicai.faculty.qualification`, `edicai.faculty.workload`, `edicai.faculty.publication`

## `edicai_fees`
- Manifest name: Fees (19.0.1.2.0) — App: yes
- Depends: account, mail, edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_grading, edicai_guardian, edicai_security, edicai_student, edicai_timetable
- Menus owned in DB: 11
- Actions used by menus (owned): 7
- Security groups defined: —
- Data models (8): `edicai.fee.payment`, `edicai.fee.accounting.config`, `edicai.fee.copilot`, `edicai.fee.structure`, `edicai.fee.structure.line`, `edicai.fee.invoice.batch.wizard`, `edicai.fee.invoice`, `edicai.fee.invoice.line`
- Extends (3): `edicai.fee.invoice`, `account.partial.reconcile`, `edicai.student`

## `edicai_finance_report`
- Manifest name: Finance Reports (19.0.1.0.0) — App: yes
- Depends: mail, edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_fees, edicai_grading, edicai_guardian, edicai_scholarship, edicai_security, edicai_student, edicai_timetable
- Menus owned in DB: 12
- Actions used by menus (owned): 8
- Security groups defined: —
- Data models (2): `edicai.finance.kpi`, `edicai.finance.snapshot`

## `edicai_gradebook`
- Manifest name: Edicai Grade Book (19.0.1.1.0) — App: yes
- Depends: edicai_assignment, edicai_grading
- Menus owned in DB: 6
- Actions used by menus (owned): 5
- Security groups defined: —
- Data models (3): `edicai.gradebook.config`, `edicai.gradebook.assignment.line`, `edicai.gradebook.student.line`
- Extends (2): `edicai.assignment.submission`, `edicai.course.offering`

## `edicai_grading`
- Manifest name: Grading & Results (19.0.1.1.0) — App: yes
- Depends: edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_guardian, edicai_security, edicai_student, edicai_timetable
- Menus owned in DB: 7
- Actions used by menus (owned): 6
- Security groups defined: —
- Data models (5): `edicai.grade.scale`, `edicai.grade.scale.line`, `grading.ai.copilot`, `edicai.grade.entry`, `edicai.semester.result`
- Extends (2): `edicai.enrollment`, `edicai.student`

## `edicai_grievance`
- Manifest name: Edicai Grievance (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_faculty_profile, edicai_guardian, edicai_notify, edicai_portal_student, edicai_portal_guardian
- Menus owned in DB: 4
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (4): `edicai.grievance.category`, `edicai.grievance.team`, `edicai.grievance.request`, `grievance.ai.copilot`

## `edicai_guardian`
- Manifest name: Edicai Guardians (19.0.1.0.0) — App: yes
- Depends: edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile
- Menus owned in DB: 2
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (2): `edicai.guardian`, `edicai.guardian.student.rel`
- Extends (1): `edicai.student`

## `edicai_hostel`
- Manifest name: Hostel (19.0.1.0.0) — App: yes
- Depends: mail, edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_security, edicai_student
- Menus owned in DB: 12
- Actions used by menus (owned): 7
- Security groups defined: —
- Data models (4): `edicai.hostel.maintenance`, `edicai.hostel.block`, `edicai.hostel.room`, `edicai.hostel.allocation`

## `edicai_institution_profile`
- Manifest name: Edicai Institution Profile (19.0.1.3.0) — App: no
- Depends: edicai_base, edicai_security, edicai_academic_generic
- Menus owned in DB: 3
- Actions used by menus (owned): 3
- Security groups defined: —
- Data models (4): `edicai.terminology.profile`, `edicai.grading.scheme`, `edicai.institution.profile`, `edicai.institution.feature`
- Extends (6): `ir.ui.view`, `res.company`, `ir.ui.menu`, `edicai.academic.unit`, `ir.actions.act_window`, `base`

## `edicai_library`
- Manifest name: Library (19.0.1.0.0) — App: yes
- Depends: mail, edicai_academic, edicai_base, edicai_campus, edicai_faculty_profile, edicai_security, edicai_student
- Menus owned in DB: 14
- Actions used by menus (owned): 10
- Security groups defined: —
- Data models (9): `library.ai.copilot`, `edicai.library.reservation`, `edicai.library.member`, `edicai.library.subject`, `edicai.library.publisher`, `edicai.library.book`, `edicai.library.author`, `edicai.library.book.copy`, `edicai.library.issue`

## `edicai_lms`
- Manifest name: Edicai LMS (1.0) — App: yes
- Depends: base, website_slides, website_sale_slides, edicai_academic, edicai_student, edicai_assignment, edicai_quiz, edicai_gradebook
- Menus owned in DB: 8
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (2): `slide.channel`, `slide.slide`

## `edicai_mentor`
- Manifest name: Edicai Student Mentor (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_faculty_profile
- Menus owned in DB: 3
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (2): `edicai.mentor.allocation`, `edicai.mentor.meeting.log`

## `edicai_notice_board`
- Manifest name: Edicai Notice Board (19.0.1.0.0) — App: yes
- Depends: mail, edicai_base, edicai_security, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_academic
- Menus owned in DB: 2
- Actions used by menus (owned): 1
- Security groups defined: —
- Data models (1): `edicai.notice`

## `edicai_notify`
- Manifest name: Notifications (19.0.1.0.0) — App: yes
- Depends: mail, edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_fees, edicai_grading, edicai_guardian, edicai_scholarship, edicai_security, edicai_student, edicai_timetable
- Menus owned in DB: 8
- Actions used by menus (owned): 5
- Security groups defined: —
- Data models (6): `edicai.notification.config`, `edicai.whatsapp.flows`, `edicai.notification.log`, `edicai.notification.engine`, `edicai.notification.template`, `edicai.notification.automation`

## `edicai_payment`
- Manifest name: Online Fee Payments (19.0.1.0.0) — App: no
- Depends: account_payment, payment, edicai_fees, edicai_portal_student
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (2): `edicai.fee.invoice`, `payment.transaction`

## `edicai_placement`
- Manifest name: Edicai Placement (19.0.1.0.0) — App: yes
- Depends: edicai_student
- Menus owned in DB: 4
- Actions used by menus (owned): 3
- Security groups defined: —
- Data models (3): `edicai.placement.company`, `edicai.placement.drive`, `edicai.placement.application`

## `edicai_portal_faculty`
- Manifest name: Edicai Faculty Portal (19.0.1.0.0) — App: yes
- Depends: edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_curriculum, edicai_timetable, edicai_admission, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_scholarship, edicai_notify, edicai_assignment, edicai_portal_student, edicai_notice_board, portal
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 

## `edicai_portal_guardian`
- Manifest name: Edicai Guardian Portal (19.0.1.0.0) — App: yes
- Depends: edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_guardian, edicai_curriculum, edicai_admission, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_notify, edicai_portal_student, edicai_notice_board, portal
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 

## `edicai_portal_student`
- Manifest name: Edicai Student Portal (19.0.1.0.0) — App: yes
- Depends: edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_calendar, edicai_student, edicai_faculty_profile, edicai_guardian, edicai_curriculum, edicai_timetable, edicai_admission, edicai_attendance, edicai_exam, edicai_grading, edicai_fees, edicai_scholarship, edicai_notify, edicai_assignment, edicai_notice_board, portal
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (1): `edicai.student`

## `edicai_progression`
- Manifest name: Edicai Progression (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_grading, edicai_attendance, edicai_curriculum
- Menus owned in DB: 2
- Actions used by menus (owned): 1
- Security groups defined: —
- Data models (1): `edicai.progression.record`

## `edicai_quiz`
- Manifest name: Edicai Quiz (19.0.1.0.0) — App: yes
- Depends: edicai_student
- Menus owned in DB: 5
- Actions used by menus (owned): 3
- Security groups defined: —
- Data models (3): `edicai.question.bank`, `edicai.quiz`, `edicai.quiz.attempt`

## `edicai_scholarship`
- Manifest name: Scholarships (19.0.1.0.0) — App: yes
- Depends: mail, edicai_academic, edicai_attendance, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_admission, edicai_exam, edicai_faculty_profile, edicai_fees, edicai_grading, edicai_guardian, edicai_security, edicai_student, edicai_timetable
- Menus owned in DB: 5
- Actions used by menus (owned): 3
- Security groups defined: —
- Data models (3): `edicai.scholarship.application`, `edicai.scholarship.program`, `edicai.scholarship.award`
- Extends (1): `edicai.student`

## `edicai_secure_transcript`
- Manifest name: Edicai Secure Transcript (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_grading, website
- Menus owned in DB: 2
- Actions used by menus (owned): 1
- Security groups defined: —
- Data models (1): `edicai.secure.transcript`

## `edicai_security`
- Manifest name: Edicai Security (19.0.1.0.0) — App: no
- Depends: edicai_base
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (1): `res.users`

## `edicai_skill_assessment`
- Manifest name: Edicai Student Skill Assessment (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_faculty_profile
- Menus owned in DB: 4
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (2): `edicai.skill`, `edicai.student.skill.assessment`

## `edicai_student`
- Manifest name: Edicai Students (19.0.1.0.0) — App: yes
- Depends: edicai_base, edicai_security, edicai_campus, edicai_academic, edicai_academic_generic, edicai_calendar
- Menus owned in DB: 4
- Actions used by menus (owned): 3
- Security groups defined: —
- Data models (4): `edicai.student.academic.history`, `edicai.student.emergency.contact`, `edicai.student`, `edicai.student.document`

## `edicai_student_leave`
- Manifest name: Edicai Student Leave Requests (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_guardian, edicai_notify, edicai_portal_student, edicai_portal_guardian
- Menus owned in DB: 3
- Actions used by menus (owned): 1
- Security groups defined: —
- Data models (1): `edicai.student.leave.request`
- Extends (1): `edicai.notification.template`

## `edicai_studio`
- Manifest name: Forge Studio — AI No-Code Platform (Odoo Studio UX Parity) (19.0.2.0.0) — App: yes
- Depends: base, mail, web, edicai_base, edicai_security
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (30): `studio.workflow`, `studio.workflow.node`, `studio.workflow.transition`, `studio.workflow.instance`, `studio.workflow.log`, `studio.dashboard`, `studio.dashboard.widget`, `studio.dsl`, `studio.model`, `studio.ai.request`, `studio.ai.operation`, `studio.field`, `studio.health`, `studio.app`, `studio.ai.copilot`, `studio.report`, `studio.report.template`, `studio.automation`, `studio.automation.log`, `studio.version`, `studio.dependency`, `studio.security.group`, `studio.security.rule`, `studio.field.permission`, `studio.view`, `studio.data.dictionary`, `studio.record`, `studio.record.value`, `studio.dataset`, `studio.expression`

## `edicai_theme`
- Manifest name: Edicai Premium Theme (19.0.1.0.0) — App: yes
- Depends: web, mail, edicai_base
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 

## `edicai_thesis`
- Manifest name: Edicai Thesis (19.0.1.0.0) — App: yes
- Depends: edicai_student, edicai_faculty_profile
- Menus owned in DB: 3
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (2): `edicai.thesis`, `edicai.thesis.review`

## `edicai_timetable`
- Manifest name: Timetable & Scheduling (19.0.1.0.0) — App: yes
- Depends: edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_curriculum, edicai_faculty_profile, edicai_guardian, edicai_security, edicai_student
- Menus owned in DB: 6
- Actions used by menus (owned): 5
- Security groups defined: —
- Data models (4): `timetable.ai.copilot`, `edicai.room.booking`, `edicai.time.slot`, `edicai.timetable.entry`

## `edicai_transport`
- Manifest name: Transport (19.0.1.0.0) — App: yes
- Depends: mail, edicai_academic, edicai_base, edicai_calendar, edicai_campus, edicai_security, edicai_student
- Menus owned in DB: 10
- Actions used by menus (owned): 6
- Security groups defined: —
- Data models (5): `edicai.transport.route`, `edicai.transport.stop`, `edicai.transport.pass`, `edicai.transport.vehicle`, `edicai.transport.trip`

## `edicai_transport_fleet`
- Manifest name: Transport Fleet Integration (19.0.1.0.0) — App: no
- Depends: fleet, edicai_transport, edicai_base
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (2): `edicai.transport.vehicle`, `fleet.vehicle`

## `edicai_web_theme`
- Manifest name: Edicai Web Theme (19.0.1.0.0) — App: no
- Depends: web
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (1): `res.config.settings`

## `edicai_website`
- Manifest name: Admissions Website (19.0.1.0.0) — App: no
- Depends: website, im_livechat, crm, edicai_admission, edicai_base
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (3): `im_livechat.channel`, `crm.lead`, `website`

## `muk_web_appsbar`
- Manifest name: MuK AppsBar (19.0.1.1.12) — App: no
- Depends: base_setup, web
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (4): `res.users`, `res.company`, `ir.http`, `res.config.settings`

## `muk_web_chatter`
- Manifest name: MuK Chatter (19.0.1.4.10) — App: no
- Depends: mail
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (3): `res.users`, `ir.http`, `mail.thread`

## `muk_web_colors`
- Manifest name: MuK Colors (19.0.1.0.9) — App: no
- Depends: web, base_setup
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (1): `muk_web_colors.color_assets_editor`
- Extends (1): `res.config.settings`

## `muk_web_dialog`
- Manifest name: MuK Dialog (19.0.1.0.11) — App: no
- Depends: web
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (2): `res.users`, `ir.http`

## `muk_web_group`
- Manifest name: MuK Groups (19.0.1.0.7) — App: no
- Depends: web
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 

## `muk_web_refresh`
- Manifest name: MuK Web Refresh (19.0.1.1.12) — App: no
- Depends: web, bus, base_automation
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (2): `ir.http`, `ir.actions.server`

## `muk_web_theme`
- Manifest name: MuK Backend Theme (19.0.1.4.9) — App: no
- Depends: muk_web_group, muk_web_chatter, muk_web_dialog, muk_web_appsbar, muk_web_colors, muk_web_refresh
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 
- Extends (3): `res.company`, `ir.http`, `res.config.settings`

## `odoo_modern_backend_full`
- Manifest name: Odoo Modern SaaS Backend UX (19.0.2.1.0) — App: yes
- Depends: web
- Menus owned in DB: 0
- Actions used by menus (owned): 0
- Security groups defined: —
- Data models (0): 

## `telegram_odoo_integration`
- Manifest name: Telegram Odoo Integration (19.0.2.0.0) — App: no
- Depends: base, sale, edicai_student, edicai_guardian
- Menus owned in DB: 2
- Actions used by menus (owned): 2
- Security groups defined: —
- Data models (5): `telegram.chat.link`, `telegram.order.session`, `telegram.session.message`, `telegram.session.attachment`, `telegram.message`
- Extends (3): `res.partner`, `sale.order`, `res.config.settings`
