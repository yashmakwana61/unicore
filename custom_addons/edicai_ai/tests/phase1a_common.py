"""Shared ORM fixtures for Phase 1A tests.

Replicates the proven edicai_* test chains (edicai_attendance /
edicai_api suites) in one place: academic core, student (+ linked
login), fee invoice, enrollment + attendance sessions, semester
results. Everything is created under record rules intact, never with
``sudo``. All methods are classmethods so HttpCase setUpClass can
reuse them directly.
"""

import odoo


class Phase1AFixtures:
    """Mixin for TransactionCase/HttpCase test classes."""

    @classmethod
    def _sandbox_company(cls, suffix=''):
        """Dedicated company for the AI suite.

        The suite must be independent from whatever data the database
        already holds (a production clone carries real applicants, real
        fee invoices and real timetable slots).  Every fixture record and
        every fixture user therefore lives in this sandbox company, so
        company-scoped tools, workflow discovery and the timetable
        overlap constraint only ever see fixture data.
        """
        cached = cls.__dict__.get('_sandbox_company_record')
        if cached is not None:
            return cached
        base = cls.env.company
        company = cls.env['res.company'].create({
            'name': 'Edicai AI Sandbox%s' % (suffix or ''),
            'currency_id': base.currency_id.id,
        })
        # Company-scoped sequences (e.g. the asset-request number) are not
        # readable from another company: mirror the main company's ones so
        # the sandbox can generate real reference numbers.
        for sequence in cls.env['ir.sequence'].search(
                [('company_id', '=', base.id)]):
            sequence.copy({'company_id': company.id})
        cls._sandbox_company_record = company
        return company

    @classmethod
    def _test_company(cls, suffix=''):
        """Company the fixtures work in (the sandbox, once built)."""
        existing = cls.__dict__.get('company')
        if existing is not None:
            return existing
        return cls._sandbox_company(suffix)

    @classmethod
    def _build_academic_core(cls, company=None, suffix=''):
        """Faculty/department/program/campus/year/semester/course."""
        company = company or cls._sandbox_company(suffix)
        cls.company = company
        # A Term-mode institution profile forces Term-based academic years
        # (edicai_calendar validation) which the semester-grain fixtures do
        # not model; detach it for the sandboxed (rolled-back) test company
        # so fixtures always build the legacy semester structure.
        profile = company.institution_profile_id
        if profile and profile.calendar_mode == 'term':
            company.institution_profile_id = False
        cls.faculty = cls.env['edicai.faculty'].create({
            'name': 'Test Faculty Sciences%s' % suffix,
            'code': 'TFS%s' % suffix,
            'company_id': company.id,
        })
        cls.department = cls.env['edicai.department'].create({
            'name': 'Test Dept Physics%s' % suffix,
            'code': 'TDP%s' % suffix,
            'faculty_id': cls.faculty.id,
            'company_id': company.id,
        })
        cls.program = cls.env['edicai.program'].create({
            'name': 'Test BSc Physics%s' % suffix,
            'code': 'TBSC%s' % suffix,
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Science',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 90,
            'program_state': 'active',
            'department_id': cls.department.id,
            'company_id': company.id,
        })
        cls.other_program = cls.env['edicai.program'].create({
            'name': 'Test BA History%s' % suffix,
            'code': 'TBAH%s' % suffix,
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 60,
            'program_state': 'active',
            'department_id': cls.department.id,
            'company_id': company.id,
        })
        cls.campus = cls.env['edicai.campus'].create({
            'name': 'Test Central Campus%s' % suffix,
            'code': 'TCC%s' % suffix,
            'company_id': company.id,
        })
        cls.academic_year = cls.env['edicai.academic.year'].create({
            'name': 'Test AY 2030-31%s' % suffix,
            'code': 'TAY%s' % suffix,
            'date_start': '2030-07-01',
            'date_end': '2031-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': company.id,
        })
        cls.semester = cls.env['edicai.semester'].create({
            'name': 'Test Semester 1%s' % suffix,
            'code': 'TS1%s' % suffix,
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2030-07-15',
            'date_end': '2030-11-30',
            'semester_state': 'ongoing',
            'company_id': company.id,
        })
        cls.semester2 = cls.env['edicai.semester'].create({
            'name': 'Test Semester 1%s Alt' % suffix,
            'code': 'TS1A%s' % suffix,
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2030-07-15',
            'date_end': '2030-11-30',
            'semester_state': 'ongoing',
            'company_id': company.id,
        })
        cls.course = cls.env['edicai.course'].create({
            'name': 'Test Classical Mechanics%s' % suffix,
            'code': 'TCM%s' % suffix,
            'credit_hours': 3.0,
            'department_id': cls.department.id,
            'company_id': company.id,
        })
        return cls

    @classmethod
    def _create_offering(cls, company=None, suffix=''):
        company = company or cls._test_company(suffix)
        cls.offering = cls.env['edicai.course.offering'].create({
            'course_id': cls.course.id,
            'semester_id': cls.semester.id,
            'academic_year_id': cls.academic_year.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'company_id': company.id,
        })
        return cls.offering

    @classmethod
    def _build_room_chain(cls, company=None, suffix=''):
        """Building/floor/room/time slot/faculty member, then one
        confirmed timetable entry (requires _create_offering first)."""
        company = company or cls._test_company(suffix)
        # NOTE: the test DB ships campus-less 'Period N' template slots
        # covering 9:00-16:15, and the overlap constraint treats
        # campus-less slots as colliding with every campus — so the
        # fixture slot uses a free early-morning window instead.
        cls.time_slot = cls.env['edicai.time.slot'].create({
            'name': 'Test Morning Slot%s' % suffix,
            'company_id': company.id,
            'campus_id': cls.campus.id,
            'start_time': 7.5,
            'end_time': 8.5,
            'slot_type': 'lecture',
        })
        cls.building = cls.env['edicai.building'].create({
            'name': 'Test Building%s' % suffix,
            'code': 'TB%s' % suffix,
            'campus_id': cls.campus.id,
            'building_type': 'academic',
            'company_id': company.id,
        })
        cls.floor = cls.env['edicai.floor'].create({
            'name': 'Test Ground Floor%s' % suffix,
            'floor_number': 0,
            'building_id': cls.building.id,
            'company_id': company.id,
        })
        cls.room = cls.env['edicai.room'].create({
            'name': 'Test Room 42%s' % suffix,
            'code': 'TR%s' % suffix,
            'floor_id': cls.floor.id,
            'room_type': 'classroom',
            'capacity': 40,
            'campus_id': cls.campus.id,
            'company_id': company.id,
        })
        cls.faculty_member = cls.env['edicai.faculty.member'].create({
            'name': 'Test',
            'last_name': 'Lecturer%s' % suffix,
            'gender': 'male',
            'email': 'lecturer%s@test.edu' % suffix,
            'mobile': '+918888777777',
            'company_id': company.id,
            'department_id': cls.department.id,
            'designation': 'professor',
            'employment_type': 'full_time',
            'joining_date': '2019-01-01',
            'member_state': 'active',
        })
        cls.timetable_entry = cls.env['edicai.timetable.entry'].create({
            'course_offering_id': cls.offering.id,
            'day_of_week': '1',
            'time_slot_id': cls.time_slot.id,
            'room_id': cls.room.id,
            'instructor_id': cls.faculty_member.id,
            'entry_state': 'confirmed',
        })
        return cls

    @classmethod
    def _create_student(cls, login_suffix='', company=None, name='Fixture',
                        last_name='Student', program=None, campus=None):
        """Create a student + linked PORTAL user (billing partner).

        ``edicai_base.group_edicai_student`` implies ``base.group_portal``
        and portal/internal groups are mutually exclusive, so a student
        login can never hold ``edicai_ai.group_edicai_ai_user``. Student
        users therefore exercise the restricted-student handler scope
        (direct handler calls); conversational chat turns run as staff
        users, which is also what the backend-only chatbot implies.
        """
        company = company or cls._test_company()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        user = Users.create({
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'name': '%s %s' % (name, last_name),
            'login': 'fixture_user_%s' % login_suffix,
            'email': 'fixture_%s@test.edu' % login_suffix,
            'password': 'fixture_pwd_1!',
            'group_ids': [
                (4, cls.env.ref('edicai_base.group_edicai_student').id),
            ],
        })
        student = cls.env['edicai.student'].create({
            'name': name,
            'last_name': last_name,
            'gender': 'male',
            'date_of_birth': '2003-02-01',
            'email': 'student_%s@test.edu' % login_suffix,
            'mobile': '+917777000111',
            'company_id': company.id,
            'campus_id': (campus or cls.campus).id,
            'program_id': (program or cls.program).id,
            'batch_year': 2030,
            'admission_date': '2030-06-01',
            'student_state': 'active',
        })
        # Billing partner link = the same channel the record rules use.
        student.partner_id = user.partner_id.id
        return student, user

    @classmethod
    def _create_staff_user(cls, login_suffix='', groups=('staff',)):
        """Staff-side user with the AI user group."""
        company = cls._test_company()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        group_ids = [
            (4, cls.env.ref('edicai_ai.group_edicai_ai_user').id),
        ]
        for group in groups:
            group_ids.append(
                (4, cls.env.ref('edicai_base.group_edicai_%s' % group).id))
        return Users.create({
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'name': 'Fixture Staff %s' % login_suffix,
            'login': 'fixture_staff_%s' % login_suffix,
            'email': 'staff_%s@test.edu' % login_suffix,
            'password': 'staff_pwd_1!',
            'group_ids': group_ids,
        })

    @classmethod
    def _create_enrollment(cls, student, offering=None):
        student.action_enroll()
        return cls.env['edicai.enrollment'].create({
            'student_id': student.id,
            'course_offering_id': (offering or cls.offering).id,
        })

    @classmethod
    def _add_attendance_session(cls, date_str, status='present',
                                student=None, offering=None):
        """One attendance session closed with the given student status."""
        enrollment = cls.env['edicai.enrollment'].search([
            ('student_id', '=', student.id),
            ('course_offering_id', '=', (offering or cls.offering).id),
        ], limit=1)
        if not enrollment:
            enrollment = cls._create_enrollment(
                student, offering or cls.offering)
        session = cls.env['edicai.attendance.session'].create({
            'timetable_entry_id': cls.timetable_entry.id,
            'session_date': date_str,
        })
        session.action_open_for_marking()
        record = cls.env['edicai.attendance.record'].search([
            ('student_id', '=', student.id),
            ('session_id', '=', session.id),
        ], limit=1)
        record.status = status
        session.with_context(
            force_write_closed_session=True).action_close_session()
        return record

    @classmethod
    def _ensure_attendance_policy(cls, min_pct=75.0, warning_pct=80.0):
        """One GLOBAL attendance policy so stored ``shortage_alert``
        computes actually fire for fixture records (no policy → no
        alert, whatever the percentages are)."""
        existing = cls.env['edicai.attendance.policy'].search([
            ('company_id', '=', cls.company.id),
            ('policy_scope', '=', 'global'),
            ('active', '=', True),
        ], limit=1)
        if existing:
            return existing
        return cls.env['edicai.attendance.policy'].create({
            'name': 'Fixture Global Attendance Policy 75/80',
            'company_id': cls.company.id,
            'policy_scope': 'global',
            'min_attendance_percentage': min_pct,
            'warning_threshold_percentage': warning_pct,
        })

    @classmethod
    def _create_fee_invoice(cls, student, amount=12500.0,
                            semester=None, company=None, suffix=''):
        company = company or cls._test_company()
        return cls.env['edicai.fee.invoice'].create({
            'student_id': student.id,
            'company_id': company.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': (semester or cls.semester).id,
            'invoice_date': odoo.fields.Date.today(),
            'due_date': odoo.fields.Date.today(),
            'currency_id': company.currency_id.id,
            'line_ids': [(0, 0, {
                'fee_type': 'tuition',
                'name': 'Tuition%s' % suffix,
                'amount': amount,
            })],
        })

    @classmethod
    def _create_semester_result(cls, student, semester=None, gpa=3.5,
                                published=True):
        return cls.env['edicai.semester.result'].create({
            'student_id': student.id,
            'company_id': cls._test_company().id,
            'semester_id': (semester or cls.semester).id,
            'credits_attempted': 20.0,
            'credits_earned': 19.0,
            'semester_gpa': gpa,
            'result_status': 'pass',
            'is_published': published,
        })
