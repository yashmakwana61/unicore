"""Phase 3: unified admission -> enrollment flow (Enroll in Program wizard).

Verifies the ``oacis.admission.enrollment.wizard`` end to end:
- default lines pre-fill from the applicant's current curriculum (mandatory
  Semester-1 courses only);
- offerings resolve scoped to program + campus + company + open state;
- confirming the wizard moves the student admitted -> enrolled -> active,
  creates the program-level ``oacis.admission.enrollment`` record and the
  course registrations, and links them;
- full offerings route to the waitlist (line kept checked), missing offerings
  are flagged and skipped (never fatal);
- offering resolution is isolated per company.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('oacis', 'unit')
class OacisAdmissionEnrollmentWizardTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # ----------------------------------------------------------
        # ACADEMIC STRUCTURE (program A — standard intake)
        # ----------------------------------------------------------

        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Wizard Campus',
            'code': 'WZC',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': '2026-2027',
            'code': '2026',
            'date_start': '2026-06-01',
            'date_end': '2027-05-31',
        })
        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Semester 1 2026-27',
            'code': 'S1-2627',
            'academic_year_id': cls.academic_year.id,
            'sequence': 1,
            'date_start': '2026-09-01',
            'date_end': '2027-01-31',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        faculty = cls.env['oacis.faculty'].create({
            'name': 'Faculty of Science',
            'code': 'WZFS',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'Physics',
            'code': 'WZPH',
            'faculty_id': faculty.id,
        })
        department = cls.department
        cls.program = cls.env['oacis.program'].create({
            'name': 'Wizard B.Sc. Physics',
            'code': 'WZBSC',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Science',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'department_id': department.id,
            'company_id': cls.company.id,
        })
        cls.cycle = cls.env['oacis.admission.cycle'].create({
            'name': 'Wizard Intake 2026-27',
            'code': 'WZI-2627',
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2026-03-01',
            'end_date': '2026-08-31',
            'state': 'active',
            'company_id': cls.company.id,
        })
        cls.env['oacis.admission.cycle.seat'].create({
            'cycle_id': cls.cycle.id,
            'program_id': cls.program.id,
            'total_seats': 30,
            'company_id': cls.company.id,
        })

        # Courses
        def _course(name, code):
            return cls.env['oacis.course'].create({
                'name': name,
                'code': code,
                'department_id': department.id,
                'course_state': 'active',
                'credit_hours': 4,
                'internal_assessment_marks': 40,
                'external_assessment_marks': 60,
                'total_marks': 100,
                'passing_marks': 40,
                'company_id': cls.company.id,
            })

        cls.course_mechanics = _course('Mechanics', 'PHY101')
        cls.course_waves = _course('Waves', 'PHY102')
        cls.course_elective = _course('Astronomy', 'PHY103')

        # Current curriculum: two mandatory Semester-1 courses + an elective
        # (Semester 1) + a mandatory Semester-2 course (must be excluded).
        cls.curriculum = cls.env['oacis.curriculum'].create({
            'name': 'B.Sc. Physics 2026',
            'program_id': cls.program.id,
            'version': '1.0',
            'is_current': True,
        })
        cls.env['oacis.curriculum.line'].create([
            {
                'curriculum_id': cls.curriculum.id,
                'course_id': cls.course_mechanics.id,
                'semester_number': 1,
                'is_mandatory': True,
            },
            {
                'curriculum_id': cls.curriculum.id,
                'course_id': cls.course_waves.id,
                'semester_number': 1,
                'is_mandatory': True,
            },
            {
                'curriculum_id': cls.curriculum.id,
                'course_id': cls.course_elective.id,
                'semester_number': 1,
                'is_mandatory': False,
            },
            {
                'curriculum_id': cls.curriculum.id,
                'course_id': cls.env['oacis.course'].create({
                    'name': 'Thermodynamics',
                    'code': 'PHY201',
                    'department_id': department.id,
                    'course_state': 'active',
                    'credit_hours': 4,
                    'company_id': cls.company.id,
                }).id,
                'semester_number': 2,
                'is_mandatory': True,
            },
        ])

        # Open offerings for the two mandatory Semester-1 courses.
        cls.offering_mechanics = cls.env['oacis.course.offering'].create({
            'course_id': cls.course_mechanics.id,
            'program_id': cls.program.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'max_enrollment': 30,
            'company_id': cls.company.id,
        })
        cls.offering_waves = cls.env['oacis.course.offering'].create({
            'course_id': cls.course_waves.id,
            'program_id': cls.program.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'max_enrollment': 30,
            'company_id': cls.company.id,
        })

        # ----------------------------------------------------------
        # Program B — full offering -> waitlist routing
        # ----------------------------------------------------------

        cls.program_full = cls.env['oacis.program'].create({
            'name': 'Wizard B.Tech ECE',
            'code': 'WZECE',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Technology',
            'credit_system': 'credit_hours',
            'duration_years': 4.0,
            'total_credits': 160,
            'department_id': department.id,
            'company_id': cls.company.id,
        })
        cls.course_full = cls.env['oacis.course'].create({
            'name': 'Signals',
            'code': 'ECE101',
            'department_id': department.id,
            'course_state': 'active',
            'credit_hours': 4,
            'company_id': cls.company.id,
        })
        cls.curriculum_full = cls.env['oacis.curriculum'].create({
            'name': 'B.Tech ECE 2026',
            'program_id': cls.program_full.id,
            'version': '1.0',
            'is_current': True,
        })
        cls.env['oacis.curriculum.line'].create({
            'curriculum_id': cls.curriculum_full.id,
            'course_id': cls.course_full.id,
            'semester_number': 1,
            'is_mandatory': True,
        })
        cls.offering_full = cls.env['oacis.course.offering'].create({
            'course_id': cls.course_full.id,
            'program_id': cls.program_full.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'min_enrollment': 1,
            'max_enrollment': 1,
            'company_id': cls.company.id,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _open_wizard(self, applicant):
        """Instantiate the wizard exactly as the applicant smart button does."""
        return self.env['oacis.admission.enrollment.wizard'].with_context(
            default_applicant_id=applicant.id,
        ).create({'applicant_id': applicant.id})

    def _confirmed_applicant(self, program, email, name='Wizard Applicant'):
        """Create + confirm an applicant (state fee_pending -> confirmed),
        which also creates the linked student record."""
        applicant = self.env['oacis.admission.applicant'].create({
            'name': name,
            'email': email,
            'mobile': '9122000000',
            'gender': 'male',
            'date_of_birth': date(2005, 3, 10),
            'cycle_id': self.cycle.id,
            'campus_id': self.campus.id,
            'program_id': program.id,
            'company_id': self.company.id,
        })
        applicant.write({'state': 'fee_pending'})
        applicant.action_confirm_admission()
        self.assertEqual(applicant.state, 'confirmed')
        self.assertTrue(applicant.student_id)
        return applicant

    # ------------------------------------------------------------------
    # Line pre-fill
    # ------------------------------------------------------------------

    def test_01_wizard_prefills_mandatory_sem1_courses(self):
        """Default lines = mandatory Semester-1 courses, offerings resolved."""
        applicant = self._confirmed_applicant(self.program, 'wz1@example.com')
        wizard = self._open_wizard(applicant)

        self.assertTrue(wizard.semester_id, 'Semester should be defaulted')
        self.assertEqual(wizard.semester_id, self.semester)

        lines = wizard.line_ids
        # Mandatory Semester-1 only: Mechanics + Waves (elective + sem-2 out).
        self.assertEqual(len(lines), 2)
        got_courses = lines.mapped('course_id')
        self.assertIn(self.course_mechanics, got_courses)
        self.assertIn(self.course_waves, got_courses)
        self.assertNotIn(self.course_elective, got_courses)

        for line in lines:
            self.assertEqual(line.offering_state, 'resolved')
            self.assertTrue(line.offering_id)
            self.assertTrue(line.checked)
            self.assertEqual(line.semester_number, 1)

    def test_02_confirm_enrolls_student_creates_enrollments(self):
        """Confirm: student -> active, program enrollment 'enrolled',
        course registrations created and linked to the program enrollment."""
        applicant = self._confirmed_applicant(self.program, 'wz2@example.com')
        wizard = self._open_wizard(applicant)

        res = wizard.action_confirm()

        # 1) Student ladder: admitted -> enrolled -> active.
        student = applicant.student_id
        self.assertEqual(student.student_state, 'active')
        self.assertEqual(student.current_semester_id, self.semester)

        # 2) Program-level admission enrollment record.
        self.assertEqual(res['res_model'], 'oacis.admission.enrollment')
        admission_enrollment = self.env['oacis.admission.enrollment'].browse(
            res['res_id'])
        self.assertTrue(admission_enrollment.name)
        self.assertTrue(
            admission_enrollment.name.startswith('AEN/'),
            'Admission enrollment number should start with AEN/. '
            'Got: %s' % admission_enrollment.name,
        )
        self.assertEqual(admission_enrollment.applicant_id, applicant)
        self.assertEqual(admission_enrollment.student_id, student)
        self.assertEqual(admission_enrollment.semester_id, self.semester)
        self.assertEqual(admission_enrollment.enrollment_state, 'enrolled')

        # 3) Course registrations created + linked.
        enrollments = self.env['oacis.enrollment'].search([
            ('admission_enrollment_id', '=', admission_enrollment.id),
        ])
        self.assertEqual(len(enrollments), 2)
        self.assertTrue(all(
            e.enrollment_state == 'registered' for e in enrollments))
        self.assertTrue(all(
            e.student_id == student for e in enrollments))

        # 4) Counters stay in sync on the applicant side.
        self.assertEqual(applicant.admission_enrollment_count, 1)
        self.assertEqual(len(applicant.student_course_enrollment_ids),
                         len(student.enrollment_ids))
        self.assertEqual(len(student.enrollment_ids), 2)

    def test_03_full_offering_routes_to_waitlist(self):
        """A full offering keeps its line checked; confirming adds the
        student to the waitlist and leaves the program enrollment pending
        when no other course could be registered."""
        # Fill the single-seat offering with another student first.
        filler = self.env['oacis.student'].create({
            'name': 'Filler',
            'last_name': 'Student',
            'gender': 'male',
            'date_of_birth': date(2004, 8, 1),
            'email': 'filler@example.com',
            'mobile': '9122111111',
            'company_id': self.company.id,
            'campus_id': self.campus.id,
            'program_id': self.program_full.id,
            'batch_year': 2026,
            'admission_date': '2026-06-01',
        })
        filler.action_enroll()
        self.env['oacis.enrollment'].create({
            'student_id': filler.id,
            'course_offering_id': self.offering_full.id,
        })
        self.assertEqual(self.offering_full.enrolled_count, 1)

        applicant = self._confirmed_applicant(
            self.program_full, 'wz3@example.com')
        wizard = self._open_wizard(applicant)
        self.assertEqual(len(wizard.line_ids), 1)
        line = wizard.line_ids
        self.assertEqual(line.offering_state, 'full')
        self.assertTrue(line.checked, 'Full lines stay checked for waitlist')

        wizard.action_confirm()

        waitlist = self.env['oacis.enrollment.waitlist'].search([
            ('course_offering_id', '=', self.offering_full.id),
            ('student_id', '=', applicant.student_id.id),
        ])
        self.assertEqual(len(waitlist), 1)
        # The filler holds the only seat; this applicant is first in queue.
        self.assertEqual(waitlist.position, 1)

        # Nothing was registered -> program enrollment remains pending.
        admission_enrollment = applicant.admission_enrollment_ids
        self.assertEqual(len(admission_enrollment), 1)
        self.assertEqual(admission_enrollment.enrollment_state, 'pending')

    def test_04_missing_offering_is_skipped_not_fatal(self):
        """A mandatory course with no open offering is flagged 'no_offering',
        unchecked, and skipped on confirm without raising."""
        program = self.env['oacis.program'].create({
            'name': 'Wizard B.A. History',
            'code': 'WZBAH',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'department_id': self.department.id,
            'company_id': self.company.id,
        })
        course = self.env['oacis.course'].create({
            'name': 'Ancient History',
            'code': 'HIS101',
            'department_id': self.course_mechanics.department_id.id,
            'course_state': 'active',
            'credit_hours': 4,
            'company_id': self.company.id,
        })
        curriculum = self.env['oacis.curriculum'].create({
            'name': 'B.A. History 2026',
            'program_id': program.id,
            'version': '1.0',
            'is_current': True,
        })
        self.env['oacis.curriculum.line'].create({
            'curriculum_id': curriculum.id,
            'course_id': course.id,
            'semester_number': 1,
            'is_mandatory': True,
        })

        applicant = self._confirmed_applicant(program, 'wz4@example.com')
        wizard = self._open_wizard(applicant)
        self.assertEqual(len(wizard.line_ids), 1)
        line = wizard.line_ids
        self.assertEqual(line.offering_state, 'no_offering')
        self.assertFalse(line.checked)

        # Confirm must not raise, and must not register anything.
        wizard.action_confirm()
        self.assertEqual(
            applicant.admission_enrollment_ids.enrollment_state, 'pending')
        self.assertEqual(
            self.env['oacis.enrollment'].search_count([
                ('student_id', '=', applicant.student_id.id),
            ]), 0)

    def test_05_offering_resolution_is_company_scoped(self):
        """An offering in another company is invisible to the wizard."""
        company_b = self.env['res.company'].create({
            'name': 'Wizard Branch B',
        })
        campus_b = self.env['oacis.campus'].create({
            'name': 'Branch B Campus',
            'code': 'WZB',
            'company_id': company_b.id,
        })
        year_b = self.env['oacis.academic.year'].create({
            'name': '2028-2029 B',
            'code': '2028B',
            'date_start': '2028-06-01',
            'date_end': '2029-05-31',
        })
        semester_b = self.env['oacis.semester'].create({
            'name': 'Sem 1 2028-29 B',
            'code': 'S1B',
            'academic_year_id': year_b.id,
            'sequence': 1,
            'date_start': '2028-09-01',
            'date_end': '2029-01-31',
            'semester_state': 'ongoing',
            'company_id': company_b.id,
        })
        # Only a company-B offering exists for this course.
        self.env['oacis.course.offering'].create({
            'course_id': self.course_mechanics.id,
            'program_id': self.program.id,
            'academic_year_id': year_b.id,
            'semester_id': semester_b.id,
            'campus_id': campus_b.id,
            'offering_state': 'open',
            'max_enrollment': 30,
            'company_id': company_b.id,
        })
        # Sanity: the B offering exists and is open, yet must not leak.
        self.assertEqual(
            self.env['oacis.course.offering'].search_count([
                ('course_id', '=', self.course_mechanics.id),
                ('offering_state', '=', 'open'),
            ]), 2)

        # Applicant in company A: their offering is the A one (open), and a
        # B-scoped resolve would be wrong. Verify the wizard's resolution uses
        # the applicant company by checking _resolve_offering directly.
        applicant = self._confirmed_applicant(self.program, 'wz5@example.com')
        wizard = self._open_wizard(applicant)
        sem_a = wizard.semester_id

        # Wizard line for Mechanics resolved from company A only.
        line = wizard.line_ids.filtered(
            lambda l: l.course_id == self.course_mechanics)
        self.assertTrue(line.offering_id)
        self.assertEqual(line.offering_id.company_id, self.company)
        self.assertEqual(line.offering_id, self.offering_mechanics)

        # Direct resolve check: with semester B, no A-company offering exists
        # -> no_offering (the B offering must not be picked up).
        self.assertFalse(
            wizard._resolve_offering(applicant, line.curriculum_line_id,
                                     semester_b))
