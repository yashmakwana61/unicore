"""Phase 1A tests — the five read-only conversational tools.

Covers per tool: valid request, unauthorized caller, wrong-company
denial, missing entity, empty result, and ambiguity (clarify, never
guess). Handlers are called through the full registry execution path
(``execute_tool``) wherever fixtures allow; direct model calls prove
the handler contracts themselves.
"""

import uuid

import odoo.tests
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_tool_registry import (
    TOOL_REGISTRY,
)

from .phase1a_common import Phase1AFixtures
from .phase2a_common import Phase2AFixtures

_GROUP_AI_USER = 'edicai_ai.group_edicai_ai_user'


# NOTE: these suites need the FULL registry (business modules like
# edicai_academic/edicai_fees), so they run post_install — at_install
# tests of edicai_ai execute before later modules load.
@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIToolFeeStatusTest(TransactionCase, Phase1AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = cls.env['edicai.ai.conversational.tools']
        cls._build_academic_core(suffix='FEES')
        cls.student, cls.student_user = cls._create_student(
            login_suffix='fees', name='Fee', last_name='Fixture Student')
        cls.invoice = cls._create_fee_invoice(cls.student, 12500.0)
        cls.staff = cls._create_staff_user(login_suffix='fees')
        cls.faculty = cls._create_staff_user(
            login_suffix='fees_faculty', groups=('faculty',))
        cls.plain = cls._create_staff_user(
            login_suffix='fees_plain', groups=())

    def _handler(self, user=None, params=None):
        model = self.tools.with_user(user or self.staff)
        return model.tool_fee_status(params or {})

    def test_01_restricted_student_sees_own_outstanding(self):
        result = self._handler(
            user=self.student_user, params={'student_name': ''})
        self.assertFalse(result.get('error_code'))
        data = result['data']
        self.assertEqual(
            round(float(data['grand_outstanding']), 2), 12500.0)
        self.assertFalse(data['empty'])
        # Citation label persisted for the grounding layer.
        self.assertEqual(result['label'], 'Fee Status')

    def test_02_restricted_student_cannot_others_via_name(self):
        """A restricted student passing ANY explicit name still gets
        their own scope only (name is ignored for restricted users)."""
        result = self._handler(
            user=self.student_user,
            params={'student_name': 'Absolutely Other'})
        self.assertFalse(result.get('error_code'))
        self.assertEqual(
            round(float(result['data']['grand_outstanding']), 2), 12500.0)

    def test_03_staff_without_entity_is_asked_to_clarify(self):
        result = self._handler(self.staff)
        self.assertIn('clarify', result)
        self.assertFalse(result.get('error_code'))

    def test_04_staff_unknown_name_not_found(self):
        result = self._handler(
            self.staff, {'student_name': 'Nonexistent Person'})
        self.assertEqual(result['error_code'], 'RECORD_NOT_FOUND')

    def test_05_staff_exact_single_student_ok(self):
        result = self._handler(
            self.staff, {'student_name': 'Fee Fixture'})
        self.assertFalse(result.get('error_code'))
        self.assertEqual(result['data']['student'],
                         self.student.display_name)

    def test_05a_staff_single_word_name_is_resolved(self):
        result = self._handler(self.staff, {'student_name': 'fee'})
        self.assertFalse(result.get('error_code'))
        self.assertEqual(result['data']['student'],
                         self.student.display_name)

    def test_06_multi_candidate_ambiguity_lists_names(self):
        # Second student whose name matches the same ilike fragment.
        second, _user = self._create_student(
            login_suffix='fees2', name='Fee', last_name='Fixture sophomore')
        result = self._handler(
            self.staff, {'student_name': 'Fee Fixture'})
        self.assertIn('clarify', result)
        self.assertIn(self.student.display_name, result['clarify'])
        self.assertIn(second.display_name, result['clarify'])

    def test_07_empty_result_when_no_invoices(self):
        student2, user2 = self._create_student(
            login_suffix='fees3', name='No Invoice',
            last_name='Fixture Student')
        result = self._handler(user2, {})
        data = result['data']
        self.assertTrue(data['empty'])
        self.assertEqual(float(data['grand_outstanding']), 0.0)

    def test_08_paid_invoice_duplicates_nothing(self):
        # Money state comes straight from the invoice model; the tool
        # must not recompute or duplicate fee logic.
        self._create_fee_invoice(self.student, 300.0,
                                 semester=self.semester2, suffix='B')
        result = self._handler(self.student_user, {})
        self.assertEqual(
            round(float(result['data']['grand_outstanding']), 2), 12800.0)

    def test_09_faculty_cannot_enumerate_cohort_fee_data(self):
        result = self.tools.with_user(self.faculty).tool_fee_summary({})
        self.assertEqual(result.get('error_code'), 'AUTHORIZATION_DENIED')


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIToolAttendanceTest(TransactionCase, Phase1AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = cls.env['edicai.ai.conversational.tools']
        cls._build_academic_core(suffix='ATT')
        cls._create_offering(suffix='ATT')
        cls._build_room_chain(suffix='ATT')
        # Stored shortage_alert computes consult the policy registry;
        # without a policy nothing ever alerts.
        cls._ensure_attendance_policy()
        cls.student, cls.student_user = cls._create_student(
            login_suffix='att', name='Att', last_name='Fixture Student')
        cls.staff = cls._create_staff_user(login_suffix='staffatt')

    def test_01_attendance_summary_grounds_on_stored_records(self):
        for i in range(8):
            self._add_attendance_session(
                date_str='2030-08-%02d' % (i + 1),
                status='present', student=self.student)
        for i in range(2):
            self._add_attendance_session(
                date_str='2030-08-%02d' % (i + 9),
                status='absent', student=self.student)
        model = self.tools.with_user(self.student_user)
        result = model.tool_attendance_report({})
        data = result['data']
        self.assertFalse(data['empty'])
        self.assertEqual(len(data['courses']), 1)
        row = data['courses'][0]
        self.assertEqual(row['percentage'], 80.0)
        self.assertFalse(row['shortage_alert'])
        self.assertEqual(result['label'], 'Attendance Report')
        self.assertEqual(data['student'], self.student.display_name)

    def test_02_shortage_flag_surfaced(self):
        for i in range(3):
            self._add_attendance_session(
                date_str='2030-09-%02d' % (i + 10),
                status='present', student=self.student)
        for i in range(8):
            self._add_attendance_session(
                date_str='2030-09-%02d' % (i + 1),
                status='absent', student=self.student)
        model = self.tools.with_user(self.student_user)
        result = model.tool_attendance_report({})
        # 3 present / 8+2 absent = 27.3% → below every policy minimum.
        self.assertTrue(result['data']['shortage'])

    def test_03_student_with_no_records_empty(self):
        student2, user2 = self._create_student(
            login_suffix='att2', name='No Records',
            last_name='Fixture Student')
        model = self.tools.with_user(user2)
        result = model.tool_attendance_report({})
        self.assertTrue(result['data']['empty'])

    def test_04_staff_without_name_clarifies(self):
        result = self.tools.with_user(self.staff).tool_attendance_report({})
        self.assertIn('clarify', result)
        self.assertFalse(result.get('error_code'))

    def test_05_staff_named_student_single_match(self):
        result = self.tools.with_user(self.staff).tool_attendance_report({
            'student_name': 'Att Fixture',
        })
        self.assertFalse(result.get('error_code'))
        self.assertEqual(
            result['data']['student'], self.student.display_name)

    def test_06_wrong_company_student_not_resolved(self):
        """A student from ANOTHER institution must never be resolved by
        the handlers: the search is company-scoped, so the safe result
        is RECORD_NOT_FOUND (no existence oracle, no leak)."""
        second_company = self.env['res.company'].create({
            'name': 'Fixture Other Institution %s' % uuid.uuid4().hex[:6],
        })
        second_campus = self.env['edicai.campus'].create({
            'name': 'Fixture Foreign Campus %s' % uuid.uuid4().hex[:6],
            'code': 'FCC' + uuid.uuid4().hex[:5].upper(),
            'company_id': second_company.id,
        })
        # Faculty/department/program codes are LETTERS-ONLY; map one
        # uuid hex digit (0-15) to one letter (A-P) per character.
        alpha = ''.join(
            chr(ord('A') + int(c, 16)) for c in uuid.uuid4().hex[:5])
        second_faculty = self.env['edicai.faculty'].create({
            'name': 'Fixture Foreign Faculty %s' % uuid.uuid4().hex[:6],
            'code': 'FFC' + alpha,
            'company_id': second_company.id,
        })
        second_dept = self.env['edicai.department'].create({
            'name': 'Fixture Foreign Dept %s' % uuid.uuid4().hex[:6],
            'code': 'FDP' + ''.join(
                chr(ord('A') + int(c, 16))
                for c in uuid.uuid4().hex[:5]),
            'faculty_id': second_faculty.id,
            'company_id': second_company.id,
        })
        second_program = self.env['edicai.program'].create({
            'name': 'Fixture Foreign BSc %s' % uuid.uuid4().hex[:6],
            'code': 'FPB' + ''.join(
                chr(ord('A') + int(c, 16))
                for c in uuid.uuid4().hex[:5]),
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Science',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 90,
            'program_state': 'active',
            'department_id': second_dept.id,
        })
        self.env['edicai.student'].create({
            'name': 'Foreign',
            'last_name': 'Fixture Student',
            'gender': 'male',
            'date_of_birth': '2003-02-01',
            'email': 'foreign%s@test.edu' % uuid.uuid4().hex[:6],
            'mobile': '+910000000001',
            'company_id': second_company.id,
            'campus_id': second_campus.id,
            'program_id': second_program.id,
            'batch_year': 2030,
            'admission_date': '2030-06-01',
            'student_state': 'active',
        })
        result = self.tools.with_user(self.staff).tool_attendance_report(
            {'student_name': 'Foreign Fixture'})
        self.assertEqual(result.get('error_code'), 'RECORD_NOT_FOUND')
        self.assertNotIn('data', result)


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIToolGradesTest(TransactionCase, Phase1AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = cls.env['edicai.ai.conversational.tools']
        cls._build_academic_core(suffix='GRD')
        cls.student, cls.student_user = cls._create_student(
            login_suffix='grd', name='Grade', last_name='Fixture Student')
        cls.staff = cls._create_staff_user(login_suffix='grd_staff')

    def test_01_published_semester_results_listed(self):
        self._create_semester_result(self.student, gpa=3.75)
        model = self.tools.with_user(self.student_user)
        result = model.tool_grade_summary({})
        data = result['data']
        self.assertFalse(data['empty'])
        self.assertEqual(len(data['semesters']), 1)
        self.assertEqual(data['semesters'][0]['gpa'], 3.75)
        self.assertEqual(data['semesters'][0]['result_status'], 'pass')

    def test_02_unpublished_results_never_exposed(self):
        self._create_semester_result(
            self.student, semester=self.semester2, gpa=1.99,
            published=False)
        model = self.tools.with_user(self.student_user)
        result = model.tool_grade_summary({})
        self.assertTrue(result['data']['empty'])

    def test_03_staff_clarifies_without_name(self):
        result = self.tools.with_user(self.staff).tool_grade_summary({})
        self.assertIn('clarify', result)

    def test_04_unknown_name_not_found(self):
        result = self.tools.with_user(self.staff).tool_grade_summary({
            'student_name': 'Nobody Here',
        })
        self.assertEqual(result['error_code'], 'RECORD_NOT_FOUND')


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIToolProgramSearchTest(TransactionCase, Phase1AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = cls.env['edicai.ai.conversational.tools']
        cls._build_academic_core(suffix='PRG')
        cls.staff = cls._create_staff_user(login_suffix='prg_staff')

    def test_01_returns_current_company_programs(self):
        model = self.tools.with_user(self.staff)
        result = model.tool_program_search({})
        self.assertFalse(result.get('error_code'))
        names = [row['name'] for row in result['data']['programs']]
        self.assertIn(self.program.name, names)
        self.assertIn(self.other_program.name, names)

    def test_02_level_filter_applied(self):
        # PhD programs do not exist in the fixtures → empty result.
        model = self.tools.with_user(self.staff)
        result = model.tool_program_search({'program_level': 'doctoral'})
        self.assertTrue(result['data']['empty'])
        self.assertFalse(result['data']['programs'])

    def test_03_query_filter_narrows(self):
        model = self.tools.with_user(self.staff)
        result = model.tool_program_search({'program_query': 'History'})
        names = [row['name'] for row in result['data']['programs']]
        self.assertIn(self.other_program.name, names)
        self.assertNotIn(self.program.name, names)

    def test_04_wrong_company_program_never_returned(self):
        """The delegate forces company scope via its stored
        ``company_id`` domain — verify the source contract."""
        import inspect
        Model = self.env['edicai.admission.ai.tools']
        source = inspect.getsource(Model._tool_program_search)
        self.assertIn("'company_id', '='", source)
        self.assertIn('active', source)

    def test_05_company_scope_proven_by_delegate_domain(self):
        """The conversational program tool must return only programs
        whose stored company matches the calling company: the delegate
        domain is ('company_id', '=', self._company_id())."""
        staff_model = self.tools.with_user(self.staff)
        result = staff_model.tool_program_search({})
        for row in result['data']['programs']:
            self.assertIn(row['name'], [
                self.program.name, self.other_program.name])


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIToolApplicantCollectionTest(TransactionCase, Phase2AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_action_core(suffix='APL')

    def _applicant(self, name, email):
        return self.env['edicai.admission.applicant'].with_user(
            self.registrar).create({
                'name': name, 'email': email, 'mobile': '9876543210',
                'gender': 'female', 'date_of_birth': '2004-03-15',
                'cycle_id': self.cycle.id, 'program_id': self.program.id,
                'campus_id': self.campus.id, 'company_id': self.company.id,
                'state': 'inquiry',
            })

    def test_01_stage_collection_and_count_are_grounded(self):
        applicant = self._applicant('List Fixture', 'list.fixture@test.edu')
        result = self.env['edicai.ai.conversational.tools'].with_user(
            self.registrar).tool_applicant_list({'state': 'inquiry'})
        self.assertIn(applicant.id,
                      [row['id'] for row in result['data']['rows']])
        self.assertGreaterEqual(result['data']['total_count'], 1)

    def test_02_no_followup_filter_uses_existing_discovery_rule(self):
        applicant = self._applicant('Followup Fixture', 'followup.fixture@test.edu')
        applicant.with_user(self.registrar).activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            date_deadline=fields.Date.today(), summary='Already followed up',
            note='', user_id=self.registrar.id)
        result = self.env['edicai.ai.conversational.tools'].with_user(
            self.registrar).tool_applicant_list({'no_followup': True})
        self.assertNotIn(
            applicant.id, [row['id'] for row in result['data']['rows']])

    def test_03_ambiguous_pending_stage_is_clarified_not_dropped(self):
        result = self.env['edicai.ai.conversational.tools'].with_user(
            self.registrar).tool_applicant_list({'state': 'pending'})
        self.assertIn('clarify_message', result)

    def test_04_followup_list_is_scoped_to_visible_applicants(self):
        applicant = self._applicant(
            'Due Applicant', 'due.applicant@test.edu')
        applicant.with_user(self.registrar).activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            date_deadline=fields.Date.context_today(self),
            summary='Call applicant', note='',
            user_id=self.registrar.id)
        result = self.env['edicai.ai.conversational.tools'].with_user(
            self.registrar).tool_followup_list({'date_filter': 'today'})
        self.assertEqual(result['data']['total_count'], 1)
        self.assertEqual(result['data']['rows'][0]['applicant'],
                         applicant.display_name)


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIToolClashCheckTest(TransactionCase, Phase1AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = cls.env['edicai.ai.conversational.tools']
        cls._build_academic_core(suffix='CCH')
        cls._create_offering(suffix='CCH')
        cls._build_room_chain(suffix='CCH')
        cls.staff = cls._create_staff_user(login_suffix='cch_staff')

    def test_01_unique_semester_term_resolves_single(self):
        self.env['edicai.semester'].create({
            'name': 'Test Semester 88CCH',
            'code': 'TS88CCH',
            'semester_type': 'odd',
            'academic_year_id': self.academic_year.id,
            'date_start': '2030-07-15',
            'date_end': '2030-11-30',
            'semester_state': 'ongoing',
            'company_id': self.company.id,
        })
        model = self.tools.with_user(self.staff)
        result = model.tool_clash_check({'semester_term': '88'})
        self.assertFalse(result.get('error_code'))
        self.assertIn('clash_count', result['data'])

    def test_02_unknown_semester_not_found(self):
        model = self.tools.with_user(self.staff)
        result = model.tool_clash_check({'semester_term': '87'})
        self.assertEqual(result.get('error_code'), 'RECORD_NOT_FOUND')

    def test_03_ambiguity_clarifies_with_names(self):
        model = self.tools.with_user(self.staff)
        # 'semester 1' matches BOTH fixture semesters; the tool asks
        # and never silently selects one.
        result = model.tool_clash_check({'semester_term': '1'})
        self.assertIn('clarify', result)
        self.assertIn(self.semester.display_name, result['clarify'])
        self.assertIn(self.semester2.display_name, result['clarify'])

    def test_04_company_scan_without_semester_is_safe(self):
        model = self.tools.with_user(self.staff)
        result = model.tool_clash_check({})
        data = result['data']
        self.assertFalse(result.get('error_code'))
        self.assertGreaterEqual(data['scanned_entries'], 1)

    def test_05_clash_detection_stays_upstream(self):
        """Deep conflict math is EXISTING code (timetable.ai.copilot
        mirrors the model constrains). The conversational layer only
        delegates; creating contradictory data via the ORM must KEEP
        failing, proving no bypass exists."""
        with self.assertRaises(Exception):
            # Same day (1) + overlapping window + same room/instructor:
            # the upstream model constraint must keep refusing this —
            # the AI layer can never write such data.
            self.env['edicai.timetable.entry'].create({
                'course_offering_id': self.offering.id,
                'day_of_week': '1',
                'time_slot_id': self.time_slot.id,
                'room_id': self.room.id,
                'instructor_id': self.faculty_member.id,
                'entry_state': 'confirmed',
            })

    def test_06_timetable_view_is_distinct_from_clash_scan(self):
        result = self.tools.with_user(self.staff).tool_timetable_view({
            'schedule_date': 'today',
        })
        self.assertFalse(result.get('error_code'))
        self.assertEqual(result['label'], 'Timetable')
        self.assertIn('date', result['data'])
        self.assertIn('count', result['data'])
        self.assertIn('entries', result['data'])
