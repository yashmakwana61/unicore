{
    'name': 'UniCore Student Enrollment',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student course registration, waitlist management and add/drop processing',
    'description': """
UniCore Student Enrollment Module
====================================

This module provides three core concepts for university enrollment management:

1. **Enrollment** (`unicore.enrollment`): The actual record of a student registered
   into a course offering for a semester. Carries the full validation history
   including prerequisite check results, schedule conflict check results, and
   grade status (stubbed for future unicore_grading module).

2. **Waitlist** (`unicore.enrollment.waitlist`): A queue entry created automatically
   when a student tries to enroll in a full offering. Registrar staff manually
   promote waitlisted students to confirmed enrollments when seats become available.

3. **Enrollment Log** (`unicore.enrollment.log`): An append-only audit record created
   automatically every time an enrollment changes state. This exists for compliance
   and accreditation record-keeping.

Validation Chain
-----------------
On enrollment creation, a 6-step validation chain is executed:

1. **Offering State** — must be 'open' for enrollment
2. **Student Eligibility** — must be in 'enrolled' or 'active' state
3. **Prerequisite Check** — all mandatory prerequisites must have a passing grade
4. **Duplicate Check** — no existing active enrollment for same student+course+semester
5. **Schedule Conflict** — no overlapping day-of-week + time-slot with other enrolled courses
6. **Seat Capacity** — if full, auto-routes to waitlist (unless auto_waitlist=False context)
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base',
        'unicore_security',
        'unicore_campus',
        'unicore_academic',
        'unicore_calendar',
        'unicore_student',
        'unicore_faculty_profile',
        'unicore_guardian',
        'unicore_curriculum',
        'unicore_timetable',
    ],
    'data': [
        'security/unicore_enrollment_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_enrollment_sequence_data.xml',
        'views/unicore_enrollment_views.xml',
        'views/unicore_enrollment_waitlist_views.xml',
        'views/unicore_enrollment_log_views.xml',
        'views/unicore_course_offering_ext_views.xml',
        'views/unicore_student_ext_enrollment_views.xml',
        'menus/unicore_enrollment_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
