{
    'name': 'Attendance Management',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Session attendance tracking, policy enforcement and shortage alerts',
    'description': """
UniCore Attendance Management
=============================

This module provides comprehensive attendance management for UniCore ERP,
built around four core concepts:

1. **Attendance Session** - Represents one actual class session that took place
   (or is scheduled to take place) on a specific date. Sessions are generated
   from unicore.timetable.entry records by the Generate Sessions wizard, with
   holiday dates automatically excluded. Faculty open a session, mark attendance
   for enrolled students, then close it.

2. **Attendance Record** - One student's attendance status for one class session.
   Records are created in bulk when a session is opened for marking. Faculty
   update the status field (Present, Absent, Late, Excused) for each student.
   Closed sessions lock their records. Cumulative per-student stats across all
   sessions in the semester for the same course offering are computed.

3. **Attendance Policy** - Defines institutional attendance requirements per
   course type or per specific course offering. Policies set the minimum
   attendance percentage required for a student to be eligible for examinations
   and academic progression. Policies follow a priority resolution chain:
   Specific Offering > Specific Course > Course Type > Global.

4. **Shortage Alert** - Automatically computed on each attendance record,
   comparing the student's cumulative attendance percentage against the
   applicable policy thresholds. A shortage_alert flag fires when the student
   falls below the minimum threshold, and a warning_alert fires when the
   student is between the warning and minimum thresholds.

Key Features:
- Automatic session generation from timetable entries with holiday exclusion
- Campus-specific holiday detection
- Batch attendance marking per session
- Cumulative per-student attendance statistics per course offering
- Multi-level attendance policies with priority resolution
- Automatic shortage and warning alerts
- Session lifecycle: Scheduled → Open for Marking → Closed / Cancelled
- Reopening support for admin corrections
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
        'unicore_enrollment',
    ],
    'data': [
        'security/unicore_attendance_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_attendance_policy_data.xml',
        'wizards/unicore_generate_sessions_wizard_views.xml',
        'views/unicore_attendance_policy_views.xml',
        'views/unicore_attendance_session_views.xml',
        'views/unicore_attendance_record_views.xml',
        'views/attendance_search_list_phase1.xml',
        'views/attendance_calendar_phase1.xml',
        'menus/unicore_attendance_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_attendance,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
