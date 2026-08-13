import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisAttendanceTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'Test Faculty of Business',
            'code': 'TFB',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'Test Management',
            'code': 'TMGMT',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'Test BBA',
            'code': 'TEST-BBA',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Business Administration',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 90,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Test Business Campus',
            'code': 'TBIZCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': 'Test AY 2028-29',
            'code': 'TAY2829',
            'date_start': '2028-07-01',
            'date_end': '2029-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Test SEM1 BBA',
            'code': 'TSEM1-BBA',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2028-07-15',
            'date_end': '2028-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        cls.course = cls.env['oacis.course'].create({
            'name': 'Test Principles of Management',
            'code': 'TPM101',
            'credit_hours': 3.0,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.offering = cls.env['oacis.course.offering'].create({
            'course_id': cls.course.id,
            'semester_id': cls.semester.id,
            'academic_year_id': cls.academic_year.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'company_id': cls.company.id,
        })
        cls.student = cls.env['oacis.student'].create({
            'name': 'Attendance',
            'last_name': 'Test Student',
            'gender': 'male',
            'date_of_birth': '2002-01-05',
            'email': 'attendance.test@example.com',
            'mobile': '+914444444444',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2028,
            'admission_date': '2028-06-01',
        })

        cls.policy = cls.env['oacis.attendance.policy'].create({
            'name': 'Test 75% Policy',
            'company_id': cls.company.id,
            'policy_scope': 'global',
            'min_attendance_percentage': 75.0,
            'warning_threshold_percentage': 80.0,
            'is_exam_eligibility_linked': True,
        })

        cls.time_slot = cls.env['oacis.time.slot'].create({
            'name': 'Test Night Slot',
            'company_id': cls.company.id,
            'start_time': 22.0,
            'end_time': 23.0,
            'slot_type': 'lecture',
        })

        cls.building = cls.env['oacis.building'].create({
            'name': 'Test Main Building',
            'code': 'TMB',
            'campus_id': cls.campus.id,
            'building_type': 'academic',
            'company_id': cls.company.id,
        })
        cls.floor = cls.env['oacis.floor'].create({
            'name': 'Test Ground Floor',
            'floor_number': 0,
            'building_id': cls.building.id,
            'company_id': cls.company.id,
        })
        cls.room = cls.env['oacis.room'].create({
            'name': 'Test Room 101',
            'code': 'TR101',
            'floor_id': cls.floor.id,
            'room_type': 'classroom',
            'capacity': 60,
            'campus_id': cls.campus.id,
            'company_id': cls.company.id,
        })

        cls.faculty_member = cls.env['oacis.faculty.member'].create({
            'name': 'Test',
            'last_name': 'Professor',
            'gender': 'male',
            'email': 'prof@test.edu',
            'mobile': '+919999999999',
            'company_id': cls.company.id,
            'department_id': cls.department.id,
            'designation': 'professor',
            'employment_type': 'full_time',
            'joining_date': '2020-01-01',
            'member_state': 'active',
        })

        cls.timetable_entry = cls.env['oacis.timetable.entry'].create({
            'course_offering_id': cls.offering.id,
            'day_of_week': '1',
            'time_slot_id': cls.time_slot.id,
            'room_id': cls.room.id,
            'instructor_id': cls.faculty_member.id,
            'entry_state': 'confirmed',
        })

    def setUp(self):
        super().setUp()
        self.student.action_enroll()
        self.env['oacis.enrollment'].create({
            'student_id': self.student.id,
            'course_offering_id': self.offering.id,
        })

    def test_01_attendance_record_create(self):
        session = self.env['oacis.attendance.session'].create({
            'timetable_entry_id': self.timetable_entry.id,
            'session_date': '2028-08-01',
        })
        session.action_open_for_marking()
        record = self.env['oacis.attendance.record'].search([
            ('student_id', '=', self.student.id),
            ('session_id', '=', session.id),
        ], limit=1)
        self.assertTrue(record)
        self.assertEqual(record.status, 'absent')

    def test_02_attendance_percentage_computation(self):
        for i in range(8):
            s = self.env['oacis.attendance.session'].create({
                'timetable_entry_id': self.timetable_entry.id,
                'session_date': f'2028-08-{i + 1:02d}',
            })
            s.action_open_for_marking()
            rec = self.env['oacis.attendance.record'].search([
                ('student_id', '=', self.student.id),
                ('session_id', '=', s.id),
            ], limit=1)
            rec.status = 'present'
            s.with_context(force_write_closed_session=True).action_close_session()

        for i in range(2):
            s = self.env['oacis.attendance.session'].create({
                'timetable_entry_id': self.timetable_entry.id,
                'session_date': f'2028-08-{i + 9:02d}',
            })
            s.action_open_for_marking()
            rec = self.env['oacis.attendance.record'].search([
                ('student_id', '=', self.student.id),
                ('session_id', '=', s.id),
            ], limit=1)
            rec.status = 'absent'
            s.with_context(force_write_closed_session=True).action_close_session()

        last_record = self.env['oacis.attendance.record'].search([
            ('student_id', '=', self.student.id),
            ('course_offering_id', '=', self.offering.id),
        ], order='id desc', limit=1)
        self.assertAlmostEqual(last_record.cumulative_attendance_percentage, 80.0, places=1)

    def test_03_shortage_alert_triggers(self):
        for i in range(10):
            s = self.env['oacis.attendance.session'].create({
                'timetable_entry_id': self.timetable_entry.id,
                'session_date': f'2028-09-{i + 1:02d}',
            })
            s.action_open_for_marking()
            rec = self.env['oacis.attendance.record'].search([
                ('student_id', '=', self.student.id),
                ('session_id', '=', s.id),
            ], limit=1)
            rec.status = 'absent'
            s.with_context(force_write_closed_session=True).action_close_session()

        last_record = self.env['oacis.attendance.record'].search([
            ('student_id', '=', self.student.id),
            ('course_offering_id', '=', self.offering.id),
        ], order='id desc', limit=1)
        self.assertTrue(last_record.shortage_alert)
