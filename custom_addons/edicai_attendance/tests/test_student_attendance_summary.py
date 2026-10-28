import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('edicai', 'unit')
class EdicaiStudentAttendanceSummaryTest(TransactionCase):
    """Phase-1 student views: batched attendance summary on edicai.student."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.faculty = cls.env['edicai.faculty'].create({
            'name': 'Summary Faculty', 'code': 'SUMF',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['edicai.department'].create({
            'name': 'Summary Dept', 'code': 'SUMD',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['edicai.program'].create({
            'name': 'Summary BBA', 'code': 'SUM-BBA',
            'program_type': 'undergraduate',
            'degree_title': 'BBA', 'credit_system': 'credit_hours',
            'duration_years': 3, 'total_credits': 90,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['edicai.campus'].create({
            'name': 'Summary Campus', 'code': 'SUMCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['edicai.academic.year'].create({
            'name': 'Summary AY', 'code': 'SUMAY',
            'date_start': '2028-07-01', 'date_end': '2029-06-30',
            'year_state': 'cancelled', 'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['edicai.semester'].create({
            'name': 'Summary SEM1', 'code': 'SUMSEM1',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2028-07-15', 'date_end': '2028-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        cls.course = cls.env['edicai.course'].create({
            'name': 'Summary Course', 'code': 'SUM101',
            'credit_hours': 3.0, 'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.offering = cls.env['edicai.course.offering'].create({
            'course_id': cls.course.id, 'semester_id': cls.semester.id,
            'academic_year_id': cls.academic_year.id,
            'program_id': cls.program.id, 'campus_id': cls.campus.id,
            'offering_state': 'open', 'company_id': cls.company.id,
        })
        cls.student = cls.env['edicai.student'].create({
            'name': 'Summary', 'last_name': 'Student', 'gender': 'male',
            'date_of_birth': '2002-01-05',
            'email': 'summary.student@example.com',
            'mobile': '+915555555555',
            'company_id': cls.company.id, 'campus_id': cls.campus.id,
            'program_id': cls.program.id, 'batch_year': 2028,
            'admission_date': '2028-06-01',
        })
        cls.time_slot = cls.env['edicai.time.slot'].create({
            'name': 'Summary Slot', 'company_id': cls.company.id,
            'start_time': 6.0, 'end_time': 7.0, 'slot_type': 'lecture',
        })
        cls.building = cls.env['edicai.building'].create({
            'name': 'Summary Building', 'code': 'SMB',
            'campus_id': cls.campus.id, 'building_type': 'academic',
            'company_id': cls.company.id,
        })
        cls.floor = cls.env['edicai.floor'].create({
            'name': 'Summary Floor', 'floor_number': 0,
            'building_id': cls.building.id,
            'company_id': cls.company.id,
        })
        cls.room = cls.env['edicai.room'].create({
            'name': 'Summary Room', 'code': 'SMR101',
            'floor_id': cls.floor.id, 'room_type': 'classroom',
            'capacity': 60, 'campus_id': cls.campus.id,
            'company_id': cls.company.id,
        })
        cls.faculty_member = cls.env['edicai.faculty.member'].create({
            'name': 'Summary', 'last_name': 'Professor', 'gender': 'male',
            'email': 'summary.prof@test.edu', 'mobile': '+916666666666',
            'company_id': cls.company.id,
            'department_id': cls.department.id,
            'designation': 'professor', 'employment_type': 'full_time',
            'joining_date': '2020-01-01',
        })
        cls.timetable_entry = cls.env['edicai.timetable.entry'].create({
            'course_offering_id': cls.offering.id,
            'day_of_week': '1', 'time_slot_id': cls.time_slot.id,
            'room_id': cls.room.id,
            'instructor_id': cls.faculty_member.id,
            'entry_state': 'confirmed',
        })
        cls.student.action_enroll()
        cls.env['edicai.enrollment'].create({
            'student_id': cls.student.id,
            'course_offering_id': cls.offering.id,
        })

    def _mark(self, statuses):
        for i, status in enumerate(statuses):
            session = self.env['edicai.attendance.session'].create({
                'timetable_entry_id': self.timetable_entry.id,
                'session_date': '2028-10-%02d' % (i + 1),
            })
            session.action_open_for_marking()
            rec = self.env['edicai.attendance.record'].search([
                ('student_id', '=', self.student.id),
                ('session_id', '=', session.id),
            ], limit=1)
            rec.status = status

    def test_01_summary_math(self):
        self.assertEqual(self.student.attendance_records_count, 0)
        self.assertEqual(self.student.attendance_percentage, 0.0)
        self.assertFalse(self.student.has_attendance_shortage)
        self._mark(['present'] * 3 + ['late'] + ['absent'] * 6)
        self.student.invalidate_recordset()
        self.assertEqual(self.student.attendance_records_count, 10)
        self.assertAlmostEqual(self.student.attendance_percentage, 40.0)
        self.assertTrue(self.student.has_attendance_shortage)

    def test_02_open_attendance_action(self):
        self._mark(['present'])
        action = self.student.action_open_attendance()
        self.assertEqual(action['res_model'], 'edicai.attendance.record')
        self.assertEqual(
            action['domain'], [('student_id', '=', self.student.id)])
