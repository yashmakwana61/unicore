Edicai Academic Structure
==========================

Defines the complete academic hierarchy for Edicai ERP.

Academic Hierarchy
------------------
Faculty (School/College)
  └── Department
        └── Program (Degree/Diploma/Certificate)
              └── Specialisation (Major/Branch)

Model Details
-------------
- edicai.faculty: Academic school/college within the institution
- edicai.department: Department within a faculty
- edicai.program: Degree, diploma or certificate program
- edicai.specialisation: Optional major or branch within a program

State Workflows
---------------
- Faculty: Draft → Operational → Suspended → Closed
- Department: Draft → Operational → Suspended → Closed
- Program: Draft → Approved → Active → Discontinued

Key Features
------------
- Multi-campus assignment for faculties, departments and programs
- Dean/HOD/Coordinator assignment from res.users
- Full accreditation tracking with expiry monitoring
- Tuition fee configuration (base rate per semester)
- Configurable credit systems and duration
- Demo data with sample Engineering and Business faculties

Dependencies
------------
- edicai_base: Base models, security groups, mixins
- edicai_security: Record rules and data isolation
- edicai_campus: Campus model for campus assignments

Security Groups Access
----------------------
- Administrator: Full CRUD on all models
- Manager: Read, write, create (no delete)
- Registrar: Read, write (no create, no delete)
- Staff: Read only
- Faculty: Read only
- Student: Read only

Author: Precisefect Solutions Pvt. Ltd.
Website: https://precisefect.com
License: LGPL-3
