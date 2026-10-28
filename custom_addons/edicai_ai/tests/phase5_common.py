"""Shared Phase 5 test infrastructure.

Builds on the proven Phase 2A fixtures (academic core + users) and
adds the REAL deterministic attendance chain this slice reads:

* one global attendance policy per company (75/80 defaults from
  ``edicai_attendance`` — never invented thresholds),
* students enrolled in course offerings, closed attendance sessions
  with explicit statuses (present/absent) through the module's own
  canonical path (``action_open_for_marking`` → mark →
  ``action_close_session``),
* a faculty user LINKED to the fixture instructor's partner (the
  channel the attendance record rules use for students' own rows;
  staff-side users are company-scoped by the repository's rule
  union),
* a full auxiliary second-company chain (fixture factory state,
  built under the admin env like Phase 3's foreign company) for
  cross-company isolation,
* chat sessions per user.

Everything is created through canonical envs — never ``sudo`` —
except the auxiliary-company fixture factory (non-conversational
state, same as Phase 3).
"""

from datetime import date, timedelta

from odoo.addons.edicai_ai.tests.phase2a_common import (
    ALL_AI_FLAGS,
    FLAG_CONVERSATION_LLM,
    FLAG_LLM_COMPOSITION,
    FLAG_ORCHESTRATOR,
    Phase2AFixtures,  # noqa: F401 — fixture chain base
)

FLAG_ACTION_WRITE = 'edicai_ai.action_write_enabled'
FLAG_ACTION_FOLLOWUP = 'edicai_ai.action_followup_enabled'
FLAG_WORKFLOW = 'edicai_ai.workflow_enabled'
FLAG_APPROVAL = 'edicai_ai.approval_enabled'
FLAG_PROACTIVE = 'edicai_ai.proactive_enabled'


def _date(month, day):
    """A fixture date inside the open 2030 semester."""
    return '2030-%02d-%02d' % (month, day)


class Phase5Fixtures(Phase2AFixtures):
    """Mixin for Phase 5 test classes."""

    @classmethod
    def _build_proactive_core(cls, suffix='PQF', day=1):
        """Academic core + rooms + proactive flag + survey users.

        All non-proactive AI flags are explicitly OFF so this
        harness never depends on parameter leakage from other test
        classes (isolation).
        """
        cls._build_action_core(suffix=suffix)
        cls._create_offering(suffix=suffix)
        cls._build_room_chain(suffix=suffix)
        cls._set_ai_flag(FLAG_ORCHESTRATOR, 'True')
        cls._set_ai_flag(FLAG_PROACTIVE, 'True')
        for flag in (FLAG_ACTION_WRITE, FLAG_ACTION_FOLLOWUP,
                     FLAG_WORKFLOW, FLAG_APPROVAL,
                     FLAG_CONVERSATION_LLM, FLAG_LLM_COMPOSITION):
            cls._set_ai_flag(flag, 'False')

        # Users: the surface groups of the slice.  The registrar and
        # the bare staff bystander come from the Phase 2A core.
        cls.p5_registrar = cls.registrar
        cls.p5_bystander = cls.bare_staff
        cls.p5_admin = cls._create_staff_user(
            login_suffix='%sadm' % suffix, groups=('admin',))
        cls.p5_faculty = cls._create_staff_user(
            login_suffix='%sfac' % suffix, groups=('faculty',))
        cls.p5_faculty_b = cls._create_staff_user(
            login_suffix='%sfb' % suffix, groups=('faculty',))
        # An AI-LEVEL manager (reads every insight row, writes none).
        cls.p5_manager = cls._create_company_user(
            '%smgr' % suffix, cls.company, groups=('manager',))
        cls.p5_manager.group_ids = [(
            4, cls.env.ref('edicai_ai.group_edicai_ai_manager').id)]

        # Record-rule links: the faculty users must be the PARTNER
        # the timetable instructors point at (same channel the
        # attendance record rules use for faculty scoping).
        cls.faculty_member.partner_id = cls.p5_faculty.partner_id.id
        cls.faculty_member_b = cls.env['edicai.faculty.member'].create({
            'name': 'Test',
            'last_name': 'Profb%s' % suffix,
            'gender': 'male',
            'email': 'profb%s@test.edu' % suffix,
            'mobile': '+918888777778',
            'company_id': cls.company.id,
            'department_id': cls.department.id,
            'designation': 'professor',
            'employment_type': 'full_time',
            'joining_date': '2019-01-01',
            'member_state': 'active',
        })
        cls.faculty_member_b.partner_id = cls.p5_faculty_b.partner_id.id
        cls.slot_b = cls.env['edicai.time.slot'].create({
            'name': 'Test Early Slot%s' % suffix,
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'start_time': 5.5,
            'end_time': 6.5,
            'slot_type': 'lecture',
        })
        cls.room_b = cls.env['edicai.room'].create({
            'name': 'Test Room 43%s' % suffix,
            'code': 'TRB%s' % suffix,
            'floor_id': cls.floor.id,
            'room_type': 'classroom',
            'capacity': 40,
            'campus_id': cls.campus.id,
            'company_id': cls.company.id,
        })
        cls.offering_b = cls.env['edicai.course.offering'].create({
            'course_id': cls.course.id,
            'semester_id': cls.semester.id,
            'academic_year_id': cls.academic_year.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'company_id': cls.company.id,
        })
        cls.timetable_entry_b = cls.env['edicai.timetable.entry'].create({
            'course_offering_id': cls.offering_b.id,
            'day_of_week': '3',
            'time_slot_id': cls.slot_b.id,
            'room_id': cls.room_b.id,
            'instructor_id': cls.faculty_member_b.id,
            'entry_state': 'confirmed',
        })
        cls._attendance_policy()
        return cls

    # ------------------------------------------------------------------
    # Attendance fixtures (canonical path, no sudo)
    # ------------------------------------------------------------------

    # Per-entry unique session dates: the session table enforces
    # (timetable_entry_id, session_date) uniqueness, so every fixture
    # session draws the NEXT date for its entry.
    _p5_seq = {}

    @classmethod
    def _next_date(cls, entry):
        seq = cls._p5_seq.get(entry.id, 0) + 1
        cls._p5_seq[entry.id] = seq
        return _date(8, seq)

    @classmethod
    def _attendance_policy(cls, company=None, eligibility=True):
        """One GLOBAL attendance policy (75/80 — repository defaults)."""
        company = company or cls.company
        return cls.env['edicai.attendance.policy'].create({
            'name': 'P5 Global Attendance Policy 75/80',
            'company_id': company.id,
            'policy_scope': 'global',
            'min_attendance_percentage': 75.0,
            'warning_threshold_percentage': 80.0,
            'is_exam_eligibility_linked': eligibility,
        })

    @classmethod
    def _close_session(cls, entry, date_str, student, status,
                       offering=None):
        """One canonical session: open → mark → close (lock + stats)."""
        offering = offering or cls.offering
        cls.env['edicai.enrollment'].search([
            ('student_id', '=', student.id),
            ('course_offering_id', '=', offering.id),
        ], limit=1) or cls._create_enrollment(student, offering)
        session = cls.env['edicai.attendance.session'].create({
            'timetable_entry_id': entry.id,
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
    def _make_shortage(cls, student, entry, offering):
        """Two canonical closed sessions → 50% (< 75 minimum)."""
        cls._close_session(
            entry, cls._next_date(entry), student, 'present',
            offering=offering)
        return cls._close_session(
            entry, cls._next_date(entry), student, 'absent',
            offering=offering)

    @classmethod
    def _make_present(cls, student, entry, offering=None):
        """One canonical closed session → 100% (no alert)."""
        return cls._close_session(
            entry, cls._next_date(entry), student, 'present',
            offering=offering or cls.offering)

    @classmethod
    def _open_session(cls, entry, date_str):
        """An OPEN (still scheduled → marking) session: its records
        have total_sessions_held == 0 (queued in the stored compute
        at 0%)."""
        session = cls.env['edicai.attendance.session'].create({
            'timetable_entry_id': entry.id,
            'session_date': date_str,
        })
        session.action_open_for_marking()
        return session

    # ------------------------------------------------------------------
    # Auxiliary company chain (fixture factory under the admin env —
    # NOT conversational state; same pattern as Phase 3's foreign
    # applicant company)
    # ------------------------------------------------------------------

    @classmethod
    def _build_company2_chain(cls, suffix='PQY'):
        """A complete second institution with its own shortage."""
        company2 = cls.env['res.company'].create({
            'name': 'P5 Second Institute %s' % suffix,
        })
        campus2 = cls.env['edicai.campus'].create({
            'name': 'Test East Campus%s' % suffix,
            'code': 'TEC%s' % suffix,
            'company_id': company2.id,
        })
        faculty2 = cls.env['edicai.faculty'].create({
            'name': 'Test Faculty East%s' % suffix,
            'code': 'TFE%s' % suffix,
            'company_id': company2.id,
        })
        department2 = cls.env['edicai.department'].create({
            'name': 'Test Dept East%s' % suffix,
            'code': 'TDE%s' % suffix,
            'faculty_id': faculty2.id,
            'company_id': company2.id,
        })
        program2 = cls.env['edicai.program'].create({
            'name': 'Test BBA East%s' % suffix,
            'code': 'TBBA%s' % suffix,
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Business Administration',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 90,
            'program_state': 'active',
            'department_id': department2.id,
            'company_id': company2.id,
        })
        ay2 = cls.env['edicai.academic.year'].create({
            'name': 'Test AY East 2030-31%s' % suffix,
            'code': 'TAYE%s' % suffix,
            'date_start': '2030-07-01',
            'date_end': '2031-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': company2.id,
        })
        semester2 = cls.env['edicai.semester'].create({
            'name': 'Test Semester East%s' % suffix,
            'code': 'TSE%s' % suffix,
            'semester_type': 'odd',
            'academic_year_id': ay2.id,
            'date_start': '2030-07-15',
            'date_end': '2030-11-30',
            'semester_state': 'ongoing',
            'company_id': company2.id,
        })
        course2 = cls.env['edicai.course'].create({
            'name': 'Test East Economics%s' % suffix,
            'code': 'TEE%s' % suffix,
            'credit_hours': 3.0,
            'department_id': department2.id,
            'company_id': company2.id,
        })
        offering2 = cls.env['edicai.course.offering'].create({
            'course_id': course2.id,
            'semester_id': semester2.id,
            'academic_year_id': ay2.id,
            'program_id': program2.id,
            'campus_id': campus2.id,
            'offering_state': 'open',
            'company_id': company2.id,
        })
        slot2 = cls.env['edicai.time.slot'].create({
            'name': 'Test East Slot%s' % suffix,
            'company_id': company2.id,
            'campus_id': campus2.id,
            'start_time': 5.0,
            'end_time': 6.0,
            'slot_type': 'lecture',
        })
        building2 = cls.env['edicai.building'].create({
            'name': 'Test East Building%s' % suffix,
            'code': 'TEB%s' % suffix,
            'campus_id': campus2.id,
            'building_type': 'academic',
            'company_id': company2.id,
        })
        floor2 = cls.env['edicai.floor'].create({
            'name': 'Test East Floor%s' % suffix,
            'floor_number': 0,
            'building_id': building2.id,
            'company_id': company2.id,
        })
        room2 = cls.env['edicai.room'].create({
            'name': 'Test East Room%s' % suffix,
            'code': 'TER%s' % suffix,
            'floor_id': floor2.id,
            'room_type': 'classroom',
            'capacity': 30,
            'campus_id': campus2.id,
            'company_id': company2.id,
        })
        member2 = cls.env['edicai.faculty.member'].create({
            'name': 'Test',
            'last_name': 'Eprof%s' % suffix,
            'gender': 'male',
            'email': 'eprof%s@test.edu' % suffix,
            'mobile': '+918888777779',
            'company_id': company2.id,
            'department_id': department2.id,
            'designation': 'professor',
            'employment_type': 'full_time',
            'joining_date': '2019-01-01',
            'member_state': 'active',
        })
        entry2 = cls.env['edicai.timetable.entry'].create({
            'course_offering_id': offering2.id,
            'day_of_week': '1',
            'time_slot_id': slot2.id,
            'room_id': room2.id,
            'instructor_id': member2.id,
            'entry_state': 'confirmed',
        })
        # One company2-scoped ADMIN user (their env.company anchors
        # detection in company 2).
        cls.p5_admin2 = cls._create_company_user(
            '%sadm2' % suffix, company2, groups=('admin',))
        # One company2 student with a REAL shortage (50%).
        student2 = cls.env['edicai.student'].create({
            'name': 'Rohit',
            'last_name': 'East%s' % suffix,
            'gender': 'male',
            'date_of_birth': '2003-02-02',
            'email': 'east_%s@test.edu' % suffix,
            'mobile': '+917777000222',
            'company_id': company2.id,
            'campus_id': campus2.id,
            'program_id': program2.id,
            'batch_year': 2030,
            'admission_date': '2030-06-01',
            'student_state': 'active',
        })
        cls._attendance_policy(company=company2, eligibility=False)
        cls._close_session(
            entry2, cls._next_date(entry2), student2, 'present',
            offering=offering2)
        cls._close_session(
            entry2, cls._next_date(entry2), student2, 'absent',
            offering=offering2)
        cls.q2_company = company2
        cls.q2_student = student2
        cls.q2_offering = offering2
        return cls

    @classmethod
    def _create_company_user(cls, login_suffix, company,
                             groups=('staff',)):
        """A staff-side user anchored in a SPECIFIC company."""
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        group_ids = [
            (4, cls.env.ref('edicai_ai.group_edicai_ai_user').id),
        ]
        for group in groups:
            group_ids.append(
                (4, cls.env.ref('edicai_base.group_edicai_%s' % group).id))
        return Users.create({
            'name': 'Fixture P5 %s' % login_suffix,
            'login': 'fixture_p5_%s' % login_suffix,
            'email': 'p5_%s@test.edu' % login_suffix,
            'password': 'p5_pwd_1!',
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'group_ids': group_ids,
        })

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @classmethod
    def _proactive(cls, user=None, company=None):
        """The proactive router bound to a user env + company."""
        Pro = cls.env['edicai.ai.proactive']
        if user is not None:
            Pro = Pro.with_user(user)
        if company is not None:
            Pro = Pro.with_company(company)
        return Pro

    @classmethod
    def _insight(cls, user=None, company=None):
        """The proactive router bound to a user env + company."""
        model = cls.env['edicai.ai.proactive.insight']
        if user is not None:
            model = model.with_user(user)
        if company is not None:
            model = model.with_company(company)
        return model

    @classmethod
    def _own_offering_chain(cls, code):
        """A dedicated offering/entry chain keyed by code.

        Rationale: a session marks ALL registered enrollments of its
        offering (the module's own canonical behaviour), so curated
        per-student percentages require per-student offerings.
        """
        seq = getattr(cls, '_p5_chain_seq', 0) + 1
        cls._p5_chain_seq = seq
        tag = 'P5%s' % code
        offering = cls.env['edicai.course.offering'].create({
            'course_id': cls.course.id,
            'semester_id': cls.semester.id,
            'academic_year_id': cls.academic_year.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'company_id': cls.company.id,
        })
        # find the first free 0.75h interval on this campus (the
        # campus template itself creates "Period" slots, so no fixed
        # band is safe — search the actual occupancy)
        taken = sorted(
            cls.env['edicai.time.slot'].search([
                ('company_id', '=', cls.company.id),
                ('campus_id', '=', cls.campus.id),
            ]).mapped(lambda s: (s.start_time, s.end_time)))
        span = 0.75
        start = None
        cur = 0.0
        for a, b in taken:
            if cur + span <= a:
                start = cur
                break
            cur = max(cur, b)
        if start is None:
            start = cur  # first fit after the last occupied span
        slot = cls.env['edicai.time.slot'].create({
            'name': 'Test Slot %s' % tag,
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'start_time': start,
            'end_time': start + 0.75,
            'slot_type': 'lecture',
        })
        room = cls.env['edicai.room'].create({
            'name': 'Test Room %s' % tag,
            'code': 'TR%s' % tag[:10],
            'floor_id': cls.floor.id,
            'room_type': 'classroom',
            'capacity': 20,
            'campus_id': cls.campus.id,
            'company_id': cls.company.id,
        })
        entry = cls.env['edicai.timetable.entry'].create({
            'course_offering_id': offering.id,
            'day_of_week': str(1 + seq % 6),
            'time_slot_id': slot.id,
            'room_id': room.id,
            'instructor_id': cls.faculty_member.id,
            'entry_state': 'confirmed',
        })
        return offering, entry

    @classmethod
    def own_offering(cls, suffix):
        """The dedicated offering of an ``own``-chain student."""
        return cls._own_offerings[suffix]

    @classmethod
    def _student_af(cls, login_suffix='p5a', name='Fixture', short=True,
                    entry=None, offering=None, own=False):
        """A fixture student (linked portal user) + sessions.

        short=True → real shortage (50%); short=False → healthy.
        ``own=True`` builds a dedicated offering chain so no other
        student's session can alter this student's percentages;
        otherwise the shared main chain is used (bulk / explicit).
        """
        if own:
            offering, entry = cls._own_offering_chain(
                login_suffix.upper())
            cls._own_offerings = dict(
                getattr(cls, '_own_offerings', {}))
            cls._own_offerings[login_suffix] = offering
        student, _user = cls._create_student(
            login_suffix=login_suffix, name=name,
            last_name='P5Batch')
        if short:
            cls._make_shortage(
                student, entry or cls.timetable_entry,
                offering or cls.offering)
        else:
            cls._make_present(
                student, entry or cls.timetable_entry,
                offering=offering or cls.offering)
        return student
