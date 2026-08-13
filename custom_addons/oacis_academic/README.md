Oacis Academic Structure
==========================

Defines the complete academic hierarchy for Oacis ERP.

Academic Hierarchy
------------------
Faculty (School/College)
  └── Department
        └── Program (Degree/Diploma/Certificate)
              └── Specialisation (Major/Branch)

Model Details
-------------
- oacis.faculty: Academic school/college within the institution
- oacis.department: Department within a faculty
- oacis.program: Degree, diploma or certificate program
- oacis.specialisation: Optional major or branch within a program

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
- oacis_base: Base models, security groups, mixins
- oacis_security: Record rules and data isolation
- oacis_campus: Campus model for campus assignments

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
