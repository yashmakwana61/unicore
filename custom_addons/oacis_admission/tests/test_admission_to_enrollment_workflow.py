import logging
from datetime import timedelta

from odoo import fields, tests

_logger = logging.getLogger(__name__)


@tests.tagged('oacis', 'integration', 'post_install', '-at_install')
class OacisAdmissionToEnrollmentTest(tests.common.SingleTransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        # ----------------------------------------------------------
        # ACADEMIC STRUCTURE
        # ----------------------------------------------------------

        faculty = cls.env['oacis.faculty'].create({
            'name': 'Faculty of Engineering',
            'code': 'FE',
            'company_id': cls.company.id,
        })
        department = cls.env['oacis.department'].create({
            'name': 'Computer Science',
            'code': 'CS',
            'faculty_id': faculty.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'B.Tech Computer Science',
            'code': 'BTCS',
            'degree_title': 'Bachelor of Technology',
            'program_type': 'undergraduate',
            'credit_system': 'credit_hours',
            'total_credits': 160,
            'duration_years': 4,
            'department_id': department.id,
            'company_id': cls.company.id,
        })

        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Main Campus',
            'code': 'MNC',
            'company_id': cls.company.id,
        })

        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': '2025-2026',
            'code': '2025',
            'date_start': '2025-06-01',
            'date_end': '2026-05-31',
        })

        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Odd Semester 2025-26',
            'code': 'ODD-2526',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-09-01',
            'date_end': '2026-01-31',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })

        # ----------------------------------------------------------
        # COURSE & OFFERING
        # ----------------------------------------------------------

        cls.course = cls.env['oacis.course'].create({
            'name': 'Data Structures',
            'code': 'CS201',
            'department_id': department.id,
            'course_state': 'active',
            'credit_hours': 4,
            'internal_assessment_marks': 40,
            'external_assessment_marks': 60,
            'total_marks': 100,
            'passing_marks': 40,
            'company_id': cls.company.id,
        })

        cls.faculty_member = cls.env['oacis.faculty.member'].create({
            'name': 'Prof. Johnson',
            'last_name': 'Johnson',
            'email': 'johnson@oacis.edu',
            'mobile': '2222222222',
            'gender': 'male',
            'academic_faculty_id': faculty.id,
            'department_id': department.id,
            'member_state': 'active',
            'joining_date': fields.Date.today(),
        })

        cls.offering = cls.env['oacis.course.offering'].create({
            'course_id': cls.course.id,
            'program_id': cls.program.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'max_enrollment': 30,
            'faculty_member_id': cls.faculty_member.id,
        })

        # ----------------------------------------------------------
        # ADMISSION CYCLE
        # ----------------------------------------------------------

        cls.cycle = cls.env['oacis.admission.cycle'].create({
            'name': 'Main Intake 2025-26',
            'code': 'MAIN-2526',
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2025-03-01',
            'end_date': '2025-08-31',
            'state': 'active',
            'company_id': cls.company.id,
        })

        cls.env['oacis.admission.cycle.seat'].create({
            'cycle_id': cls.cycle.id,
            'program_id': cls.program.id,
            'total_seats': 30,
            'company_id': cls.company.id,
        })

        # ----------------------------------------------------------
        # FEE STRUCTURE (only present when oacis_fees is installed)
        # ----------------------------------------------------------

        cls.fee_structure = None
        if 'oacis.fee.structure' in cls.env:
            cls.fee_structure = cls.env['oacis.fee.structure'].create({
                'name': 'B.Tech CS Semester Fees 2025-26',
                'company_id': cls.company.id,
                'academic_year_id': cls.academic_year.id,
                'semester_id': cls.semester.id,
                'program_id': cls.program.id,
                'campus_id': cls.campus.id,
                'structure_state': 'active',
            })

            cls.env['oacis.fee.structure.line'].create({
                'structure_id': cls.fee_structure.id,
                'fee_type': 'tuition',
                'name': 'Tuition Fee',
                'amount': 30000,
            })

        # ----------------------------------------------------------
        # GRADE SCALE
        # ----------------------------------------------------------

        cls.grade_scale = cls.env['oacis.grade.scale'].create({
            'name': 'Standard 4.0 Scale',
            'company_id': cls.company.id,
            'is_default': False,
            'max_gpa': 4.0,
        })
        cls.env['oacis.grade.scale.line'].create({
            'scale_id': cls.grade_scale.id,
            'letter_grade': 'A',
            'min_percentage': 80.0,
            'max_percentage': 100.0,
            'grade_point': 4.0,
            'is_passing': True,
        })
        cls.env['oacis.grade.scale.line'].create({
            'scale_id': cls.grade_scale.id,
            'letter_grade': 'B',
            'min_percentage': 60.0,
            'max_percentage': 79.99,
            'grade_point': 3.0,
            'is_passing': True,
        })
        cls.env['oacis.grade.scale.line'].create({
            'scale_id': cls.grade_scale.id,
            'letter_grade': 'C',
            'min_percentage': 40.0,
            'max_percentage': 59.99,
            'grade_point': 2.0,
            'is_passing': True,
        })
        cls.env['oacis.grade.scale.line'].create({
            'scale_id': cls.grade_scale.id,
            'letter_grade': 'F',
            'min_percentage': 0.0,
            'max_percentage': 39.99,
            'grade_point': 0.0,
            'is_passing': False,
        })

        # ----------------------------------------------------------
        # TIMETABLE INFRASTRUCTURE (for attendance test)
        # ----------------------------------------------------------

        building = cls.env['oacis.building'].create({
            'name': 'Academic Block A',
            'code': 'BLK-A',
            'campus_id': cls.campus.id,
        })
        floor = cls.env['oacis.floor'].create({
            'name': 'First Floor',
            'floor_number': 1,
            'building_id': building.id,
        })
        room = cls.env['oacis.room'].create({
            'name': 'Room 101',
            'code': 'A101',
            'floor_id': floor.id,
            'capacity': 40,
            'room_type': 'classroom',
        })
        time_slot = cls.env['oacis.time.slot'].create({
            'name': 'Slot 8-9 AM',
            'company_id': cls.company.id,
            'start_time': 8.0,
            'end_time': 9.0,
            'slot_type': 'lecture',
        })
        cls.timetable_entry = cls.env['oacis.timetable.entry'].create({
            'course_offering_id': cls.offering.id,
            'day_of_week': '1',
            'time_slot_id': time_slot.id,
            'room_id': room.id,
            'instructor_id': cls.faculty_member.id,
            'entry_state': 'confirmed',
        })

        # ----------------------------------------------------------
        # CLASS-LEVEL STATE VARIABLES
        # ----------------------------------------------------------

        cls.test_applicant = None
        cls.test_offer = None
        cls.created_student = None

    # ==============================================================
    # TEST 01: CREATE APPLICANT
    # ==============================================================

    def test_01_create_applicant(self):
        applicant = self.env['oacis.admission.applicant'].create({
            'name': 'Rahul',
            'last_name': 'Sharma',
            'email': 'rahul.sharma@test.oacis.edu',
            'mobile': '9876543210',
            'gender': 'male',
            'date_of_birth': '2000-06-15',
            'cycle_id': self.cycle.id,
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'aggregate_percentage': 85.0,
            'company_id': self.company.id,
            'state': 'applied',
        })
        self.assertTrue(applicant.application_number)
        self.assertTrue(
            applicant.application_number.startswith('APP/'),
            'Application number should start with APP/. '
            'Got: %s' % applicant.application_number,
        )
        self.__class__.test_applicant = applicant

    # ==============================================================
    # TEST 02: DOCUMENT VERIFICATION
    # ==============================================================

    def test_02_applicant_document_verification(self):
        applicant = self.__class__.test_applicant
        if not applicant:
            self.skipTest('test_01 did not run first')

        applicant.action_submit_documents()
        self.assertEqual(applicant.state, 'documents_pending')
        self.assertTrue(applicant.documents_submitted)

        applicant.action_submit_for_review()
        self.assertEqual(applicant.state, 'under_review')
        self.assertTrue(applicant.documents_verified)

    # ==============================================================
    # TEST 03: SHORTLIST
    # ==============================================================

    def test_03_applicant_shortlist(self):
        applicant = self.__class__.test_applicant
        if not applicant:
            self.skipTest('test_01 did not run first')

        applicant.action_shortlist()
        self.assertEqual(applicant.state, 'shortlisted')

    # ==============================================================
    # TEST 04: MERIT LIST
    # ==============================================================

    def test_04_applicant_merit_list(self):
        applicant = self.__class__.test_applicant
        if not applicant:
            self.skipTest('test_01 did not run first')

        applicant.action_add_to_merit()
        self.assertEqual(applicant.state, 'merit_listed')

    # ==============================================================
    # TEST 05: OFFER LETTER
    # ==============================================================

    def test_05_offer_letter_created(self):
        applicant = self.__class__.test_applicant
        if not applicant:
            self.skipTest('test_01 did not run first')

        applicant.action_send_offer()
        self.assertEqual(applicant.state, 'offer_sent')
        self.assertEqual(applicant.offer_letter_count, 1)

        offer = applicant.offer_letter_ids[0]
        self.assertTrue(
            offer.letter_number.startswith('OFR/'),
            'Offer letter number should start with OFR/. '
            'Got: %s' % offer.letter_number,
        )
        self.assertEqual(offer.state, 'draft')

        offer.action_send()
        self.assertEqual(offer.state, 'sent')

        self.__class__.test_offer = offer

    # ==============================================================
    # TEST 06: OFFER ACCEPTED
    # ==============================================================

    def test_06_offer_accepted(self):
        offer = self.__class__.test_offer
        if not offer:
            self.skipTest('test_05 did not run first')

        offer.action_accept()
        self.assertEqual(offer.state, 'accepted')
        self.assertIsNotNone(offer.response_date)

        applicant = offer.applicant_id
        self.assertEqual(applicant.state, 'fee_pending')

    # ==============================================================
    # TEST 07: ADMISSION CONFIRMED
    # ==============================================================

    def test_07_admission_confirmed_creates_student(self):
        applicant = self.__class__.test_applicant
        if not applicant:
            self.skipTest('test_01 did not run first')

        applicant.action_confirm_admission()
        self.assertEqual(applicant.state, 'confirmed')
        self.assertTrue(
            applicant.student_id,
            'Applicant should have a linked student record',
        )
        self.assertGreater(applicant.student_id.id, 0)

        self.__class__.created_student = applicant.student_id

    # ==============================================================
    # TEST 08: CREATED STUDENT DATA
    # ==============================================================

    def test_08_created_student_has_correct_data(self):
        student = self.__class__.created_student
        if not student:
            self.skipTest('test_07 did not run first')

        applicant = self.__class__.test_applicant

        self.assertEqual(
            student.program_id, applicant.program_id,
            'Student program should match applicant program',
        )
        self.assertEqual(
            student.company_id, applicant.company_id,
            'Student company should match applicant company',
        )
        self.assertTrue(
            student.student_id_number,
            'Student ID number should be generated',
        )
        self.assertTrue(
            str(student.student_id_number).startswith('STU/'),
            'Student ID should start with STU/. '
            'Got: %s' % student.student_id_number,
        )

        student.write({'student_state': 'enrolled'})
        self.assertEqual(student.student_state, 'enrolled')

    # ==============================================================
    # TEST 09: ENROLL IN COURSE
    # ==============================================================

    def test_09_enroll_student_in_course(self):
        student = self.__class__.created_student
        if not student:
            self.skipTest('test_07 did not run first')

        enrollment = self.env['oacis.enrollment'].create({
            'student_id': student.id,
            'course_offering_id': self.offering.id,
        })
        self.assertTrue(enrollment)
        self.assertEqual(enrollment.enrollment_state, 'registered')
        self.assertEqual(enrollment.student_id, student)
        self.assertEqual(enrollment.course_id, self.course)

        self.__class__.test_enrollment = enrollment

    # ==============================================================
    # TEST 10: TAKE ATTENDANCE
    # ==============================================================

    def test_10_take_attendance(self):
        student = self.__class__.created_student
        if not student:
            self.skipTest('test_07 did not run first')

        session = self.env['oacis.attendance.session'].create({
            'timetable_entry_id': self.timetable_entry.id,
            'session_date': self.semester.date_start,
            'session_state': 'open',
        })

        record = self.env['oacis.attendance.record'].create({
            'session_id': session.id,
            'student_id': student.id,
            'enrollment_id': self.__class__.test_enrollment.id,
            'status': 'present',
        })
        self.assertTrue(record)
        self.assertEqual(record.status, 'present')

    # ==============================================================
    # TEST 11: ENTER GRADE
    # ==============================================================

    def test_11_enter_grade(self):
        enrollment = self.__class__.test_enrollment
        if not enrollment:
            self.skipTest('test_09 did not run first')

        grade = self.env['oacis.grade.entry'].create({
            'enrollment_id': enrollment.id,
            'internal_marks': 35.0,
            'external_marks': 52.0,
        })
        self.assertTrue(grade)
        self.assertEqual(grade.total_marks_obtained, 87.0,
                         'total_marks_obtained should be 35 + 52 = 87')
        self.assertEqual(grade.entry_state, 'draft')

        self.__class__.test_grade = grade

    # ==============================================================
    # TEST 12: PUBLISH GRADE
    # ==============================================================

    def test_12_publish_grade(self):
        grade = self.__class__.test_grade
        if not grade:
            self.skipTest('test_11 did not run first')

        grade.write({'entry_state': 'published'})
        self.assertEqual(grade.entry_state, 'published')
        self.assertTrue(
            grade.letter_grade,
            'Letter grade should be computed. Got: %s' % grade.letter_grade,
        )
        self.assertTrue(grade.is_pass, 'Student should have passing grade')

    # ==============================================================
    # TEST 13: CREATE FEE INVOICE
    # ==============================================================

    def test_13_create_fee_invoice(self):
        student = self.__class__.created_student
        if not student:
            self.skipTest('test_07 did not run first')
        if 'oacis.fee.invoice' not in self.env:
            self.skipTest('oacis_fees not installed')

        invoice = self.env['oacis.fee.invoice'].create({
            'student_id': student.id,
            'company_id': self.company.id,
            'academic_year_id': self.academic_year.id,
            'semester_id': self.semester.id,
            'fee_structure_id': self.fee_structure.id,
            'invoice_date': fields.Date.today(),
            'due_date': fields.Date.today() + timedelta(days=30),
        })
        self.assertTrue(invoice)
        self.assertEqual(invoice.invoice_state, 'draft')
        self.assertTrue(
            invoice.invoice_number.startswith('INV/'),
            'Invoice number should start with INV/. '
            'Got: %s' % invoice.invoice_number,
        )

        self.env['oacis.fee.invoice.line'].create({
            'invoice_id': invoice.id,
            'fee_type': 'tuition',
            'name': 'Tuition Fee',
            'amount': 30000,
        })

        self.assertGreater(invoice.total_amount, 0,
                           'Invoice total amount should be > 0')

        self.__class__.test_invoice = invoice

    # ==============================================================
    # TEST 14: RECORD FEE PAYMENT
    # ==============================================================

    def test_14_record_fee_payment(self):
        invoice = self.__class__.test_invoice
        if not invoice:
            self.skipTest('test_13 did not run first')
        if 'oacis.fee.payment' not in self.env:
            self.skipTest('oacis_fees not installed')

        payment = self.env['oacis.fee.payment'].create({
            'invoice_id': invoice.id,
            'amount': 15000,
            'payment_method': 'online',
            'payment_date': fields.Date.today(),
        })
        self.assertTrue(payment)
        self.assertTrue(
            payment.receipt_number.startswith('RCP/'),
            'Receipt number should start with RCP/. '
            'Got: %s' % payment.receipt_number,
        )

        payment.action_confirm()
        self.assertEqual(payment.payment_state, 'confirmed')

        invoice.invalidate_recordset(['invoice_state'])
        self.assertEqual(invoice.invoice_state, 'partial')
        self.assertEqual(invoice.amount_paid, 15000)

    # ==============================================================
    # TEST 15: FULL LIFECYCLE COMPLETE
    # ==============================================================

    def test_15_full_lifecycle_complete(self):
        student = self.__class__.created_student
        if not student:
            self.skipTest('test_07 did not run first')

        self.assertTrue(
            student.student_id_number,
            'Student ID number must be set at end of lifecycle',
        )

        enrollment_count = self.env['oacis.enrollment'].search_count([
            ('student_id', '=', student.id),
        ])
        self.assertGreaterEqual(
            enrollment_count, 1,
            'Student must have at least 1 enrollment',
        )

        grade_count = self.env['oacis.grade.entry'].search_count([
            ('student_id', '=', student.id),
        ])
        self.assertGreaterEqual(
            grade_count, 1,
            'Student must have at least 1 grade entry',
        )

        if 'oacis.fee.invoice' in self.env:
            invoice_count = self.env['oacis.fee.invoice'].search_count([
                ('student_id', '=', student.id),
            ])
            self.assertGreaterEqual(
                invoice_count, 1,
                'Student must have at least 1 fee invoice',
            )

        self.assertGreaterEqual(
            student.cgpa, 0.0,
            'Student CGPA should be set',
        )

        _logger.info(
            'Lifecycle test complete: %s (ID: %s, CGPA: %s)',
            student.display_name,
            student.student_id_number,
            student.cgpa,
        )
