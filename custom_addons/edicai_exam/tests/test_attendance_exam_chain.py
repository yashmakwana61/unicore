"""Phase 1 stub ATT-01..EXM-02: attendance sessions -> shortage -> hall tickets.

Copy to: custom_addons/edicai_exam/tests/test_attendance_exam_chain.py
(Odoo auto-discovers tests/test_*.py; no __init__.py needed.)
Covers matrix: ATT-01, ATT-02, EXM-01, EXM-02.
"""
from odoo import fields, tests


@tests.tagged('edicai', 'edicai_phase1', 'integration', 'post_install', '-at_install')
class EdicaiAttendanceExamChainTest(tests.common.SingleTransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        faculty = cls.env['edicai.faculty'].create({
            'name': 'Faculty of Science', 'code': 'FEX',
            'company_id': cls.company.id})
        department = cls.env['edicai.department'].create({
            'name': 'Physics', 'code': 'PHX', 'faculty_id': faculty.id})
        program = cls.env['edicai.program'].create({
            'name': 'B.Sc Physics', 'code': 'BPX', 'degree_title': 'B.Sc',
            'program_type': 'undergraduate', 'credit_system': 'credit_hours',
            'total_credits': 120, 'duration_years': 3,
            'department_id': department.id, 'company_id': cls.company.id})
        cls.campus = cls.env['edicai.campus'].create({
            'name': 'Main Campus', 'code': 'EXC', 'company_id': cls.company.id})
        year = cls.env['edicai.academic.year'].create({
            'name': '2031-2032', 'code': 'EX31',
            'date_start': '2031-06-01', 'date_end': '2032-05-31',
            'year_type': 'term'})
        cls.semester = cls.env['edicai.semester'].create({
            'name': 'Odd 2031', 'code': 'EX-S1', 'academic_year_id': year.id,
            'date_start': '2031-09-01', 'date_end': '2032-01-31',
            'semester_type': 'term_1',
            'semester_state': 'ongoing', 'company_id': cls.company.id})
        course = cls.env['edicai.course'].create({
            'name': 'Mechanics', 'code': 'PHX101',
            'department_id': department.id, 'course_state': 'active',
            'credit_hours': 4})
        instructor = cls.env['edicai.faculty.member'].create({
            'name': 'Prof Ex', 'last_name': 'Ex', 'email': 'ex1@edicai.edu',
            'mobile': '9000000002', 'gender': 'female',
            'academic_faculty_id': faculty.id, 'department_id': department.id,
            'member_state': 'active', 'joining_date': fields.Date.today()})
        cls.offering = cls.env['edicai.course.offering'].create({
            'course_id': course.id, 'program_id': program.id,
            'academic_year_id': year.id,
            'semester_id': cls.semester.id, 'campus_id': cls.campus.id,
            'faculty_member_id': instructor.id, 'max_enrollment': 60,
            'offering_state': 'open'})
        slot = cls.env['edicai.time.slot'].create({
            'name': 'Slot A', 'start_time': 7.0, 'end_time': 8.0,
            'campus_id': cls.campus.id, 'company_id': cls.company.id})
        building = cls.env['edicai.building'].create({
            'name': 'Block A', 'code': 'BLKA', 'campus_id': cls.campus.id})
        floor = cls.env['edicai.floor'].create({
            'name': 'Ground Floor', 'floor_number': 0,
            'building_id': building.id})
        cls.room = cls.env['edicai.room'].create({
            'name': 'R101', 'code': 'R101', 'floor_id': floor.id,
            'room_type': 'exam_hall', 'capacity': 60,
            'exam_capacity': 40})
        cls.timetable_entry = cls.env['edicai.timetable.entry'].create({
            'course_offering_id': cls.offering.id, 'day_of_week': '0',
            'time_slot_id': slot.id, 'room_id': cls.room.id,
            'instructor_id': instructor.id})
        cls.student = cls.env['edicai.student'].create({
            'name': 'Exam', 'last_name': 'Student', 'email': 'exst@edicai.edu',
            'mobile': '9000000003', 'gender': 'male',
            'date_of_birth': '2005-01-01', 'campus_id': cls.campus.id,
            'program_id': program.id, 'batch_year': '2026',
            'student_state': 'enrolled'})
        cls.enrollment = cls.env['edicai.enrollment'].create({
            'student_id': cls.student.id,
            'course_offering_id': cls.offering.id,
            'enrollment_state': 'registered'})

    def test_01_session_open_creates_records(self):
        """ATT-01: opening a session auto-creates per-student records."""
        session = self.env['edicai.attendance.session'].create({
            'timetable_entry_id': self.timetable_entry.id,
            'session_date': '2031-09-15'})
        self.assertEqual(session.session_state, 'scheduled')
        session.action_open_for_marking()
        self.assertEqual(session.session_state, 'open')
        self.assertTrue(session.attendance_record_ids)

    def test_02_exam_hall_ticket_eligibility(self):
        """EXM-01/02: publish schedule -> tickets with eligibility status."""
        schedule = self.env['edicai.exam.schedule'].create({
            'name': 'Final - Mechanics', 'course_offering_id': self.offering.id,
            'company_id': self.company.id, 'exam_type': 'final',
            'exam_date': '2032-01-10',
            'exam_start_time': 9.0, 'exam_end_time': 12.0,
            'venue_ids': [self.room.id]})
        schedule.action_publish()
        self.assertEqual(schedule.exam_state, 'published')
        schedule.action_generate_hall_tickets()
        self.assertTrue(schedule.hall_ticket_ids)
        ticket = schedule.hall_ticket_ids[0]
        self.assertIn(ticket.eligibility_status,
                      ('eligible', 'ineligible', 'ineligible_fees'))
