"""Phase 1 stub TT-01..TT-03: timetable conflict detection + room booking.

Copy to: custom_addons/oacis_timetable/tests/test_timetable_conflicts.py
(Odoo auto-discovers tests/test_*.py; no __init__.py needed.)
Covers matrix: TT-01, TT-02, TT-03.
"""
from odoo import fields, tests
from odoo.exceptions import ValidationError


@tests.tagged('oacis', 'oacis_phase1', 'integration', 'post_install', '-at_install')
class OacisTimetableConflictTest(tests.common.SingleTransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        faculty = cls.env['oacis.faculty'].create({
            'name': 'Faculty of Engineering', 'code': 'FET',
            'company_id': cls.company.id})
        department = cls.env['oacis.department'].create({
            'name': 'Computer Science', 'code': 'CST', 'faculty_id': faculty.id})
        program = cls.env['oacis.program'].create({
            'name': 'B.Tech CS', 'code': 'BTT1', 'degree_title': 'B.Tech',
            'program_type': 'undergraduate', 'credit_system': 'credit_hours',
            'total_credits': 160, 'duration_years': 4,
            'department_id': department.id, 'company_id': cls.company.id})
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Main Campus', 'code': 'TTC', 'company_id': cls.company.id})
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': '2030-2031', 'code': 'TT30',
            'date_start': '2030-06-01', 'date_end': '2031-05-31',
            'year_type': 'term'})
        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Odd 2030', 'code': 'TT-S1',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2030-09-01', 'date_end': '2031-01-31',
            'semester_type': 'term_1',
            'semester_state': 'ongoing', 'company_id': cls.company.id})
        course_a = cls.env['oacis.course'].create({
            'name': 'Data Structures', 'code': 'TTC201',
            'department_id': department.id, 'course_state': 'active',
            'credit_hours': 4})
        course_b = cls.env['oacis.course'].create({
            'name': 'Algorithms', 'code': 'TTC202',
            'department_id': department.id, 'course_state': 'active',
            'credit_hours': 4})
        cls.instructor = cls.env['oacis.faculty.member'].create({
            'name': 'Prof Test', 'last_name': 'Test', 'email': 'tt1@oacis.edu',
            'mobile': '9000000001', 'gender': 'male',
            'academic_faculty_id': faculty.id, 'department_id': department.id,
            'member_state': 'active', 'joining_date': fields.Date.today()})
        cls.offering_a = cls.env['oacis.course.offering'].create({
            'course_id': course_a.id, 'program_id': program.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id, 'campus_id': cls.campus.id,
            'faculty_member_id': cls.instructor.id, 'max_enrollment': 60,
            'offering_state': 'open'})
        cls.offering_b = cls.env['oacis.course.offering'].create({
            'course_id': course_b.id, 'program_id': program.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id, 'campus_id': cls.campus.id,
            'faculty_member_id': cls.instructor.id, 'max_enrollment': 60,
            'offering_state': 'open'})
        cls.slot = cls.env['oacis.time.slot'].create({
            'name': 'Slot A', 'start_time': 7.0, 'end_time': 8.0,
            'campus_id': cls.campus.id, 'company_id': cls.company.id})
        building = cls.env['oacis.building'].create({
            'name': 'Block A', 'code': 'BLKA', 'campus_id': cls.campus.id})
        floor = cls.env['oacis.floor'].create({
            'name': 'Ground Floor', 'floor_number': 0,
            'building_id': building.id})
        cls.room = cls.env['oacis.room'].create({
            'name': 'R101', 'code': 'R101', 'floor_id': floor.id,
            'capacity': 60})

    def _make_entry(self, offering=None, room=None, instructor=None, day='0'):
        return self.env['oacis.timetable.entry'].create({
            'course_offering_id': (offering or self.offering_a).id,
            'day_of_week': day, 'time_slot_id': self.slot.id,
            'room_id': (room or self.room).id,
            'instructor_id': (instructor or self.instructor).id,
        })

    def test_01_room_overlap_rejected(self):
        """TT-01: same room+slot+day for another offering must raise."""
        self._make_entry(offering=self.offering_a, day='0').action_confirm()
        with self.assertRaises(ValidationError):
            self._make_entry(offering=self.offering_b, day='0')

    def test_02_instructor_double_booking_rejected(self):
        """TT-02: same instructor+slot+day in another room must raise."""
        other_room = self.room.copy({'name': 'R102', 'code': 'R102'})
        self._make_entry(offering=self.offering_a, day='1',
                         room=self.room).action_confirm()
        with self.assertRaises(ValidationError):
            self._make_entry(offering=self.offering_b, day='1',
                             room=other_room)

    def test_03_room_booking_lifecycle(self):
        """TT-03: requested>approved>cancelled booking on a free day/slot."""
        free_slot = self.env['oacis.time.slot'].create({
            'name': 'Slot Z', 'start_time': 17.0, 'end_time': 18.0,
            'campus_id': self.campus.id, 'company_id': self.company.id})
        booking = self.env['oacis.room.booking'].create({
            'name': 'Guest Lecture', 'room_id': self.room.id,
            'campus_id': self.campus.id, 'company_id': self.company.id,
            'time_slot_id': free_slot.id, 'booking_date': '2030-10-05'})
        self.assertEqual(booking.booking_state, 'requested')
        booking.action_approve()
        self.assertEqual(booking.booking_state, 'approved')
        booking.action_cancel()
        self.assertEqual(booking.booking_state, 'cancelled')
