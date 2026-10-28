"""Phase 5 — DETERMINISTIC detection tests.

Proves (prompt §25):

* a valid signal is detected when real shortage evidence exists;
* NO signal exists when the condition does not exist;
* detection is deterministic (same data → same key, twice);
* evidence + severity are exactly the repository's own semantics;
* zero-held-session rows (the stored 0% compute with nothing marked)
  are qualified away deterministically;
* record-rule scoping: faculty see ONLY their own sessions' rows;
* cross-company isolation: another institution's shortage is never
  visible;
* the detector is bounded (cap + truncated honest flag);
* unauthorized users get NOTHING (group gate, fail closed);
* detection never writes attendance records (source data unchanged).
"""

import odoo
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.tests.phase5_common import (
    Phase5Fixtures,
)


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIProactiveDetectHarness(TransactionCase, Phase5Fixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_proactive_core(suffix='PQF')
        cls._build_company2_chain()
        # Company 1: two short students in DIFFERENT instructor
        # scopes + one healthy student.
        cls.s_short = cls._student_af('p5a', 'Sameer', short=True,
                                      own=True)
        cls.s_ok = cls._student_af('p5b', 'Nikhil', short=False,
                                   own=True)
        cls.s_short_b = cls._student_af(
            'p5c', 'Anaya', short=True,
            entry=cls.timetable_entry_b, offering=cls.offering_b)
        # A student with ONLY an open (not yet closed) session — the
        # stored compute flags them at 0% with zero held sessions.
        cls.s_open, _usr = cls._create_student('p5d', name='Vikram')
        cls.env['edicai.enrollment'].create({
            'student_id': cls.s_open.id,
            'course_offering_id': cls.offering.id,
        })
        cls._open_session(
            cls.timetable_entry,
            cls._next_date(cls.timetable_entry))
        # Healthy-only third offering for a scoped faculty member.
        cls.p5_faculty_c = cls._create_staff_user(
            'p5fc', groups=('faculty',))
        cls.faculty_member_c = cls.env['edicai.faculty.member'].create({
            'name': 'Test',
            'last_name': 'ProfcPQF',
            'gender': 'male',
            'email': 'profc.pqf@test.edu',
            'mobile': '+918888777780',
            'company_id': cls.company.id,
            'department_id': cls.department.id,
            'designation': 'professor',
            'employment_type': 'full_time',
            'joining_date': '2019-01-01',
            'member_state': 'active',
        })
        cls.faculty_member_c.partner_id = cls.p5_faculty_c.partner_id.id
        cls.slot_c = cls.env['edicai.time.slot'].create({
            'name': 'Test Slot C PQF',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'start_time': 4.5,
            'end_time': 5.5,
            'slot_type': 'lecture',
        })
        cls.s_healthy_c, _usr = cls._create_student('p5e',
                                                    name='Meera')
        cls.offering_c = cls.env['edicai.course.offering'].create({
            'course_id': cls.course.id,
            'semester_id': cls.semester.id,
            'academic_year_id': cls.academic_year.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'company_id': cls.company.id,
        })
        cls.entry_c = cls.env['edicai.timetable.entry'].create({
            'course_offering_id': cls.offering_c.id,
            'day_of_week': '4',
            'time_slot_id': cls.slot_c.id,
            'room_id': cls.room_b.id,
            'instructor_id': cls.faculty_member_c.id,
            'entry_state': 'confirmed',
        })
        cls.env['edicai.enrollment'].create({
            'student_id': cls.s_healthy_c.id,
            'course_offering_id': cls.offering_c.id,
        })
        cls._close_session(
            cls.entry_c, cls._next_date(cls.entry_c),
            cls.s_healthy_c, 'present', offering=cls.offering_c)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def detect(self, user=None, company=None, offering_id=None):
        return self._proactive(user, company).detect_signal(
            user=user, session=None, offering_id=offering_id)

    def pair_set(self, signal):
        return {(r['student_id'], r['offering_id'])
                for r in signal['rows']}

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------

    def test_01_no_signal_without_condition(self):
        """The healthy-only offering yields NO signal at all
        (absence test, deterministic)."""
        signal = self.detect(
            self.p5_faculty_c, company=self.company,
            offering_id=self.offering_c.id)
        self.assertIsNotNone(signal)
        self.assertTrue(signal['cleared'])
        self.assertEqual(signal['rows'], [])
        self.assertEqual(signal['key'], False)
        self.assertIsNone(signal['severity'])

    def test_02_signal_detected_and_deterministic(self):
        """Same data → identical signal, twice."""
        one = self.detect(self.p5_registrar, company=self.company)
        two = self.detect(self.p5_registrar, company=self.company)
        self.assertIsNotNone(one)
        self.assertEqual(one['type'], 'attendance.shortage.review')
        self.assertFalse(one['cleared'])
        self.assertEqual(one['key'], two['key'])
        self.assertEqual(one['rows'], two['rows'])
        # Evidence: EXACTLY the two company-1 short pairs; the
        # healthy student and the zero-held-session student are
        # absent.
        pairs = self.pair_set(one)
        self.assertIn((self.s_short.id, self.own_offering('p5a').id),
                      pairs)
        self.assertIn((self.s_short_b.id, self.offering_b.id), pairs)
        self.assertEqual(len(pairs), 2)
        for row in one['rows']:
            self.assertIn(row['student_name'],
                          ('Sameer P5Batch', 'Anaya P5Batch'))
            self.assertEqual(row['pct'], 50.0)
            self.assertEqual(row['min_pc'], 75.0)
        # The healthy student never appears.
        self.assertNotIn((self.s_ok.id, self.own_offering('p5b').id),
                         pairs)
        # The zero-held-session student is qualified away.
        self.assertNotIn((self.s_open.id, self.offering.id), pairs)
        # The second-institution shortage NEVER crosses the company
        # boundary.
        self.assertNotIn((self.q2_student.id, self.q2_offering.id),
                         pairs)

    def test_03_severity_high_is_eligibility_linked(self):
        """Company-1 policy links attendance to exam eligibility →
        HIGH is set by the DETECTOR."""
        signal = self.detect(self.p5_registrar, company=self.company)
        self.assertEqual(signal['severity'], 'high')
        self.assertTrue(all(r['eligibility'] for r in signal['rows']))

    def test_04_severity_medium_when_not_eligibility_linked(self):
        """The second institution's policy is NOT eligibility-linked
        → MEDIUM — set by the detector, never by an LLM."""
        signal = self.detect(
            self.p5_admin2, company=self.q2_company)
        self.assertIsNotNone(signal)
        self.assertFalse(signal['cleared'])
        self.assertEqual(signal['count'], 1)
        self.assertEqual(signal['severity'], 'medium')
        self.assertFalse(
            any(r['eligibility'] for r in signal['rows']))

    def test_05_visibility_is_exactly_the_users_orm(self):
        """No AI-level bypass: the detector's pairs equal what the
        user reads THEMSELVES under the repository's record rules
        (the attendance record rules UNION the internal-user company
        rule with role rules — faculty/registrar are company-scoped,
        students own-row; the module's own semantics)."""
        for user, company in ((self.p5_faculty, self.company),
                              (self.p5_faculty_b, self.company),
                              (self.p5_admin2, self.q2_company)):
            direct = self.env['edicai.attendance.record'].with_user(
                user).search([('shortage_alert', '=', True),
                              ('company_id', '=', company.id)])
            direct_pairs = {(r.student_id.id,
                             r.course_offering_id.id or 0)
                            for r in direct
                            if r.total_sessions_held > 0}
            signal = self.detect(user, company=company)
            self.assertFalse(signal['cleared'])
            self.assertEqual(self.pair_set(signal), direct_pairs)

    def test_06_detector_bounded(self):
        """More short pairs than the cap → capped count + honest
        truncated flag (prompt §24)."""
        # 22 extra absent-only students (0% at one held session each).
        for i in range(22):
            student, _usr = self._create_student(
                'p5x%02d' % i, name='Bulk %02d' % i)
            self.env['edicai.enrollment'].create({
                'student_id': student.id,
                'course_offering_id': self.offering.id,
            })
            self._close_session(
                self.timetable_entry, self._next_date(
                    self.timetable_entry), student, 'absent')
        signal = self.detect(self.p5_registrar, company=self.company)
        from odoo.addons.edicai_ai.models.ai_proactive import DETECT_LIMIT
        # bounded: capped at the limit AFTER qualification …
        self.assertLessEqual(signal['count'], DETECT_LIMIT)
        # …the cap is FULLY consumed by 24 real pairs here…
        self.assertEqual(signal['count'], DETECT_LIMIT)
        # …and the honest overflow flag stands.
        self.assertTrue(signal['truncated'])

    def test_07_staff_user_gets_nothing(self):
        """A user without any surface group is refused BEFORE any
        data read (group gate, fail closed)."""
        signal = self._proactive(
            self.p5_bystander, company=self.company).detect_signal(
            user=self.p5_bystander, session=None)
        self.assertIsNone(signal)

    def test_08_detection_writes_nothing(self):
        """Detection is strictly read-only: attendance records,
        sessions and their states are untouched."""
        Session = self.env['edicai.attendance.session']
        Record = self.env['edicai.attendance.record']
        before_s = [r.id for r in Session.search([])]
        before_r = [(r.id, r.status) for r in Record.search([])]
        self.detect(self.p5_registrar, company=self.company)
        self.assertEqual([r.id for r in Session.search([])], before_s)
        self.assertEqual(
            [(r.id, r.status) for r in Record.search([])], before_r)
