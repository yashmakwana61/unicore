# Navigation Test Plan

A. **Integrity (OdooTestCase / tagged tests in edicai_navigation/tests)**
- Every XML ID referenced in workspaces_menus.xml resolves after full graph load.
- Exactly 11 new custom roots; custom root count in `ir.ui.menu` equals 11 + 0 (old roots are sections).
- No menu ends with missing parent (orphan check = 0).
- Every actionable menu retains its action and target model (manifest `preserve_action=yes`).
- Manifest row count equals custom menu count + 2 shortcuts; every reparented row matches DB.

B. **Role visibility (representative users)**
- Matrix roles: Super Admin, Admin, Registrar, Admissions Officer, Faculty, Exam Officer, Finance, Librarian, Hostel Mgr, Transport Mgr, Placement, Student, Guardian.
- Assert `load_menus` output per role contains the expected workspace roots and NOT others.
- Admin sees workspace 110; Registrar sees 20; Finance sees 60 (+90); Student sees only self-service.

C. **Regression (reuse existing suites)**
- Run per-module existing tests (¹ verified present in 40+ modules) for: admission flow, attendance, assignments/quiz/gradebook chain, exam scheduling, fees, scholarships, hostel, transport, library, thesis, notifications, demo generator.
- Web regression: login per role; open 3 canonical deep links per workspace; portal pages for student/guardian.

D. **Launcher behaviour**
- Odoo 19 app launcher lists exactly the 11 workspace apps for admin (custom) — verify no double apps, no leftover icons for the 31 old roots.