{
    'name': 'Examination Management',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Exam scheduling, hall tickets, seating plans and eligibility checks',
    'description': """
UniCore Examination Management
==============================

This module provides comprehensive exam management for UniCore ERP,
built around three core concepts:

- **Exam Schedule** - Defines a single examination event for a specific
  course offering. Each schedule links a course offering to an exam date,
  time, venue and duration. Multiple exam types (midterm, final,
  supplementary) can exist for the same course offering. The schedule
  acts as the root from which hall tickets and seating plans are generated.

- **Hall Ticket** - Per-student authorization to sit a specific exam.
  Generated in bulk from the exam schedule, each ticket checks the
  student's attendance eligibility against the applicable attendance
  policy. Ineligible tickets are flagged but still created - the
  registrar decides whether to override. A student cannot sit an exam
  without an approved hall ticket.

- **Seating Plan** - Assigns an eligible, approved hall ticket holder
  to a specific room and seat number. Seating is generated automatically
  by distributing students across the assigned venues based on each
  room's exam capacity. Supports manual adjustments for special
  accommodation requests.

**Key Features:**

- Exam schedule linked to course offering (not course)
- Multiple exam types per offering (midterm, final, supplementary, quiz, etc.)
- Automatic hall ticket generation with attendance eligibility check
- Attendance policy integration via unicore_attendance
- Override approval for ineligible students
- Auto-generated unique ticket numbers
- Seating plan generation with room capacity distribution
- Unique seat numbers within each room per exam
- Hall ticket state lifecycle: Draft -> Approved -> Used / Cancelled
- Exam schedule state lifecycle: Draft -> Published -> Hall Tickets Generated
  -> Seating Generated -> Ongoing -> Completed / Cancelled
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
        'unicore_attendance',
    ],
    'data': [
        'security/unicore_exam_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_exam_sequence_data.xml',
        'views/unicore_exam_hall_ticket_views.xml',
        'views/unicore_exam_seating_views.xml',
        'views/unicore_exam_schedule_views.xml',
        'views/exam_search_phase1.xml',
        'views/unicore_hall_ticket_template.xml',
        'data/unicore_hall_ticket_report_action.xml',
        'menus/unicore_exam_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_exam,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
