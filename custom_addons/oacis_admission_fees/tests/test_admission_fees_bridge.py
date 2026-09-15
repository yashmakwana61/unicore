from odoo import tests
from odoo.exceptions import UserError


@tests.tagged('oacis', 'phase_fees')
class OacisAdmissionFeesBridgeTest(tests.common.TransactionCase):
    """Phase D: admission <-> fees bridge (oacis_admission_fees module)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        faculty = cls.env['oacis.faculty'].create({
            'name': 'Faculty of Science',
            'code': 'FS',
            'company_id': cls.company.id,
        })
        department = cls.env['oacis.department'].create({
            'name': 'Physics',
            'code': 'PHY',
            'faculty_id': faculty.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'B.Sc Physics',
            'code': 'BSC-PHY',
            'degree_title': 'Bachelor of Science',
            'program_type': 'undergraduate',
            'credit_system': 'credit_hours',
            'total_credits': 120,
            'duration_years': 3,
            'department_id': department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Science Campus',
            'code': 'SC',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': '2025-2026',
            'code': '2025',
            'date_start': '2025-06-01',
            'date_end': '2026-05-31',
        })
        cls.cycle = cls.env['oacis.admission.cycle'].create({
            'name': 'Main Intake 2025-26',
            'code': 'MAIN-2526',
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2025-03-01',
            'end_date': '2026-08-31',
            'state': 'active',
            'company_id': cls.company.id,
        })
        cls.seat = cls.env['oacis.admission.cycle.seat'].create({
            'cycle_id': cls.cycle.id,
            'program_id': cls.program.id,
            'total_seats': 10,
            'reserved_seats': 0,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Semester 1',
            'code': 'SEM1-2526',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-06-15',
            'date_end': '2025-12-31',
            'semester_type': 'odd',
        })
        cls.structure = cls.env['oacis.fee.structure'].create({
            'name': 'BSC Physics 2025-26',
            'company_id': cls.company.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'currency_id': cls.company.currency_id.id,
            'structure_state': 'active',
            'fee_due_date': '2025-08-31',
            'line_ids': [
                (0, 0, {'fee_type': 'tuition', 'name': 'Tuition Fee',
                        'amount': 50000.0}),
                (0, 0, {'fee_type': 'registration', 'name': 'Registration Fee',
                        'amount': 5000.0}),
            ],
        })

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def _create_merit_applicant(self, name):
        return self.env['oacis.admission.applicant'].create({
            'name': name,
            'email': '%s@test.oacis.edu' % name.lower().replace(' ', '.'),
            'mobile': '9000000000',
            'gender': 'male',
            'date_of_birth': '2003-06-15',
            'cycle_id': self.cycle.id,
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'company_id': self.company.id,
            'state': 'merit_listed',
        })

    def _move_to_fee_pending(self, applicant):
        applicant.action_send_offer()
        offer = applicant.offer_letter_ids[0]
        offer.action_send()
        offer.action_accept()
        self.assertEqual(applicant.state, 'fee_pending')

    # ==============================================================
    # TEST 01: OFFER ACCEPT AUTO-GENERATES STUDENT + INVOICE
    # ==============================================================

    def test_01_offer_accept_generates_student_and_invoice(self):
        applicant = self._create_merit_applicant('Ria')
        self._move_to_fee_pending(applicant)

        self.assertTrue(applicant.student_id,
                        'The student must be pre-created at fee_pending.')
        self.assertEqual(applicant.fee_invoice_count, 1)
        invoice = applicant.fee_invoice_ids[0]
        self.assertEqual(invoice.applicant_id, applicant)
        self.assertEqual(invoice.semester_id, self.semester)
        self.assertEqual(invoice.fee_structure_id, self.structure)
        self.assertEqual(invoice.invoice_state, 'draft')
        self.assertEqual(len(invoice.line_ids), 2)
        self.assertEqual(invoice.total_amount, 55000.0)

    # ==============================================================
    # TEST 02: CONFIRMATION BLOCKED WHILE INVOICE UNPAID
    # ==============================================================

    def test_02_confirm_blocked_until_invoice_paid(self):
        applicant = self._create_merit_applicant('Sia')
        self._move_to_fee_pending(applicant)
        with self.assertRaises(UserError):
            applicant.action_confirm_admission()
        self.assertEqual(applicant.state, 'fee_pending')

    # ==============================================================
    # TEST 03: FULL PAYMENT AUTO-CONFIRMS ADMISSION
    # ==============================================================

    def test_03_full_payment_confirms_admission(self):
        applicant = self._create_merit_applicant('Tia')
        self._move_to_fee_pending(applicant)
        invoice = applicant.fee_invoice_ids[0]

        invoice.write({'invoice_state': 'paid'})
        invoice._confirm_applicant_if_paid()

        self.assertEqual(applicant.state, 'confirmed',
                         'A fully paid fee invoice must confirm the admission.')
        # The pre-created student must be reused, not duplicated.
        students = self.env['oacis.student'].search([
            ('admission_number', '=', applicant.application_number),
        ])
        self.assertEqual(len(students), 1)

    # ==============================================================
    # TEST 04: GENERATION IS IDEMPOTENT
    # ==============================================================

    def test_04_generation_is_idempotent(self):
        applicant = self._create_merit_applicant('Uia')
        self._move_to_fee_pending(applicant)
        applicant.action_generate_fee_invoice()
        applicant.action_generate_fee_invoice()
        self.assertEqual(applicant.fee_invoice_count, 1)

    # ==============================================================
    # TEST 05: NO STRUCTURE -> NO INVOICE, CONFIRMATION FALLS BACK
    # ==============================================================

    def test_05_no_structure_falls_back_to_legacy_confirm(self):
        other_program = self.env['oacis.program'].create({
            'name': 'B.A Economics',
            'code': 'BA-ECO',
            'degree_title': 'Bachelor of Arts',
            'program_type': 'undergraduate',
            'credit_system': 'credit_hours',
            'total_credits': 120,
            'duration_years': 3,
            'department_id': self.env['oacis.department'].search([], limit=1).id,
            'company_id': self.company.id,
        })
        applicant = self.env['oacis.admission.applicant'].create({
            'name': 'Via',
            'email': 'via@test.oacis.edu',
            'mobile': '9000000001',
            'gender': 'female',
            'date_of_birth': '2003-06-15',
            'cycle_id': self.cycle.id,
            'campus_id': self.campus.id,
            'program_id': other_program.id,
            'company_id': self.company.id,
            'state': 'merit_listed',
        })
        self._move_to_fee_pending(applicant)
        # No structure applies to this program -> no invoice generated.
        self.assertEqual(applicant.fee_invoice_count, 0)
        # Legacy confirmation path still works and creates the student.
        applicant.action_confirm_admission()
        self.assertEqual(applicant.state, 'confirmed')
        self.assertTrue(applicant.student_id)