UniCore Academic Calendar
=========================

Manages the complete academic time structure for UniCore ERP.

Time Hierarchy
--------------
Academic Year
  └── Semester (or Term / Trimester)
        └── Academic Week
              └── Holiday / Event

Model Details
-------------
- unicore.academic.year: Annual academic calendar with semester/trimester structure
- unicore.semester: Individual semester/term with key academic dates
- unicore.academic.week: Weekly breakdown within a semester
- unicore.holiday: Holiday and event tracking within academic years

State Workflows
---------------
Academic Year: Draft → Confirmed → Active/Current → Completed → (Cancelled at any time)
Semester: Draft → Confirmed → Registration Open → Ongoing → Exam Period → Completed

Key Features
------------
- Only ONE active academic year per institution enforced
- Date overlap validation across academic years
- Semester dates constrained within academic year dates
- Week dates constrained within semester dates
- Holiday dates constrained within academic year dates
- Week generation wizard with preview (auto-calculates from date range)
- get_current_year() / get_current_semester() API methods for other modules
- Is-current computed fields on year, semester, and week
- Compensatory class tracking for holidays
- Full chatter tracking on all state changes

Dependencies
------------
- unicore_base: Base models, security groups, mixins
- unicore_security: Record rules and data isolation
- unicore_campus: Campus model for multi-campus calendar
- unicore_academic: Program model for semester-program linkage

Author: Precisefect Solutions Pvt. Ltd.
Website: https://precisefect.com
License: LGPL-3
