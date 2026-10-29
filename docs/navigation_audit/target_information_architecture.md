# Target Information Architecture

Source of truth: live DB dump (268 custom menus over 11 proposed workspaces).
Every existing custom menu received exactly one canonical parent. Standard Odoo menus (427) are out of restructuring scope and stay untouched.

## Workspace roots (new module `edicai_navigation`)

- `edicai_navigation.menu_workspace_10` — **Workspace 10: Institution Management** — visible to: edicai_base.group_edicai_admin
- `edicai_navigation.menu_workspace_20` — **Workspace 20: Admissions & Enrollment** — visible to: edicai_base.group_edicai_registrar,base.group_system
- `edicai_navigation.menu_workspace_30` — **Workspace 30: Student Lifecycle** — visible to: edicai_base.group_edicai_staff,edicai_base.group_edicai_registrar,edicai_base.group_edicai_faculty,edicai_base.group_edicai_student,edicai_base.group_edicai_manager
- `edicai_navigation.menu_workspace_40` — **Workspace 40: Teaching & Learning** — visible to: edicai_base.group_edicai_faculty,edicai_base.group_edicai_staff
- `edicai_navigation.menu_workspace_50` — **Workspace 50: Examinations & Scheduling** — visible to: edicai_base.group_edicai_registrar,edicai_base.group_edicai_manager,base.group_system
- `edicai_navigation.menu_workspace_60` — **Workspace 60: Finance & Scholarships** — visible to: edicai_base.group_edicai_finance,edicai_base.group_edicai_manager
- `edicai_navigation.menu_workspace_70` — **Workspace 70: Campus Operations** — visible to: edicai_base.group_edicai_staff,edicai_base.group_edicai_manager
- `edicai_navigation.menu_workspace_80` — **Workspace 80: Careers & Research** — visible to: edicai_base.group_edicai_staff,edicai_base.group_edicai_manager
- `edicai_navigation.menu_workspace_90` — **Workspace 90: Insights & Reports** — visible to: edicai_base.group_edicai_manager,edicai_base.group_edicai_finance,edicai_base.group_edicai_registrar,base.group_system
- `edicai_navigation.menu_workspace_100` — **Workspace 100: Communication & AI** — visible to: base.group_user
- `edicai_navigation.menu_workspace_110` — **Workspace 110: Administration & Integrations** — visible to: edicai_base.group_edicai_admin,base.group_system

## Canonical mapping (current app root → workspace)

- `menu_edicai_admission_root` → Workspace 20 Admissions & Enrollment
- `menu_edicai_asset_request_root` → Workspace 70 Campus Operations
- `menu_edicai_digital_library_root` → Workspace 70 Campus Operations
- `menu_edicai_hostel_root` → Workspace 70 Campus Operations
- `menu_edicai_library_root` → Workspace 70 Campus Operations
- `menu_edicai_transport_root` → Workspace 70 Campus Operations
- `menu_edicai_placement_root` → Workspace 80 Careers & Research
- `menu_edicai_skill_root` → Workspace 80 Careers & Research
- `menu_edicai_thesis_root` → Workspace 80 Careers & Research
- `menu_edicai_appointment_root` → Workspace 100 Communication & AI
- `menu_edicai_documents_root` → Workspace 100 Communication & AI
- `menu_edicai_ai_root` → Workspace 100 Communication & AI
- `menu_edicai_notice_root` → Workspace 100 Communication & AI
- `menu_edicai_notify_root` → Workspace 100 Communication & AI
- `menu_edicai_exam` → Workspace 50 Examinations & Scheduling
- `menu_edicai_grading` → Workspace 50 Examinations & Scheduling
- `menu_edicai_timetable` → Workspace 50 Examinations & Scheduling
- `menu_edicai_fees_root` → Workspace 60 Finance & Scholarships
- `menu_edicai_scholarship_root` → Workspace 60 Finance & Scholarships
- `menu_edicai_analytics_root` → Workspace 90 Insights & Reports
- `menu_edicai_finance_report_root` → Workspace 90 Insights & Reports
- `menu_edicai_attendance` → Workspace 30 Student Lifecycle
- `menu_edicai_discipline_root` → Workspace 30 Student Lifecycle
- `menu_edicai_grievance_root` → Workspace 30 Student Lifecycle
- `menu_edicai_mentor_root` → Workspace 30 Student Lifecycle
- `menu_edicai_progression_root` → Workspace 30 Student Lifecycle
- `menu_edicai_secure_transcript_root` → Workspace 30 Student Lifecycle
- `menu_edicai_lms_root` → Workspace 40 Teaching & Learning
- `menu_edicai_assignment` → Workspace 40 Teaching & Learning
- `menu_edicai_quiz_root` → Workspace 40 Teaching & Learning

## Edicai root dismantling

- `menu_edicai_root` record is **kept** (XML-ID stability) but its direct sections are re-parented into workspaces; a childless grouping menu is not rendered by the webclient, so the old "Edicai" app disappears without any deletion.

## Contextual shortcuts (reuse actions, no duplicates)

- `edicai_navigation.menu_ws40_my_assignment_scores` → Workspace 40, reusing `edicai_gradebook.action_edicai_my_assignment_scores` — Contextual access from Teaching & Learning; canonical entry under Workspace 50 > Grading.
- `edicai_navigation.menu_ws30_my_fees` → Workspace 30, reusing `edicai_fees.action_edicai_fees_student` — Student self-service entry from Student Lifecycle; canonical under Workspace 60 > Fees.

## Deviations & pending approvals

- Grading & Results: canonical in Workspace 50 (Exam Officer view), shortcuts in 40 for teaching view — per prompt validation point.
- Finance dashboards (`edicai_finance_report`) live in Workspace 90; operational fee screens stay in 60.
- Demo Data stays inside Workspace 10 → Configuration (per prompt list), marked admin-only.
- Website administration stays in standard Odoo area (per prompt).
- Each workspace may host its own Configuration subsection — kept, pushed to highest sequence inside the workspace (rule 5).
- Seven role groups proposed for genuine gaps (see role matrix).