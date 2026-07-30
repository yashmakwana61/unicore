{
    'name': 'Timetable & Scheduling',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Class scheduling, time slots and conflict-free timetable generation',
    'description': """
UniCore Timetable & Scheduling Module
=======================================

This module provides three core concepts for university timetable management:

1. **Time Slot** (`unicore.time.slot`): Reusable bell-schedule period definitions
   shared across the entire institution. Time slots are day-agnostic templates
   (e.g. "Period 1: 09:00-10:00") that form the building blocks of the daily
   schedule. The same time slot template applies Monday through Saturday.

2. **Timetable Entry** (`unicore.timetable.entry`): One single recurring scheduled
   class session linking a course offering to a specific day-of-week, time slot,
   room, and instructor. Entries recur weekly for the duration of the semester
   (or a configurable sub-range within it).

3. **Room Booking** (`unicore.room.booking`): A one-off, non-recurring room
   reservation separate from the regular weekly timetable — e.g. guest lectures,
   makeup classes, or special events.

Conflict Detection Philosophy
-----------------------------
A conflict exists when two records compete for the same (room OR instructor
OR offering-section) on the same day-of-week AND overlapping time slot AND
overlapping date range. Three independent conflict checks are enforced:

- Room conflict — same room, same day, same slot, overlapping date range
- Instructor conflict — same faculty member (primary OR co-instructor),
  same day, same slot, overlapping date range
- Section conflict — same course offering, same day, same slot
  (a section cannot have two different classes scheduled in parallel)

Room bookings are cross-checked against both other bookings and recurring
timetable entries to prevent double-booking.
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
    ],
    'data': [
        'security/unicore_timetable_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_time_slot_demo_data.xml',
        'views/unicore_time_slot_views.xml',
        'views/unicore_timetable_entry_views.xml',
        'views/timetable_search_calendar_phase1.xml',
        'views/unicore_room_booking_views.xml',
        'menus/unicore_timetable_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_timetable,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
