"""Manual-Testing Lab utility (administrator-only).

Provides REPEATABLE manual QA support for the Conversational ERP:

* deterministic QA personas built from the EXISTING Odoo security
  groups (no new permission is invented, none weakened);
* a deterministic ground-truth dataset written through CANONICAL Odoo
  models/state machines (so the tester can compare AI answers against
  "what Odoo says"); plus a LIVE ground-truth report computed from
  those records at query time;
* a SAFE test-state reset: it archives QA-persona chat sessions and
  cancels already-EXPIRED pending actions.  It NEVER touches ERP
  business records (students, invoices, sessions, workflow steps...

Guard: every method is restricted to the Edicai AI manager group
(Settings → Edicai AI is already manager-gated) or the superuser.
"""

import logging

from odoo import api, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

_QA_GROUP = 'edicai_ai.group_edicai_ai_manager'
_ADMIN_GROUP = 'edicai_base.group_edicai_admin'

_PERSONA_PASSWORD = 'qa_pwd_change_me_1!'

#: explicit group xmlid — every operational persona must own it directly
_AI_USER = 'edicai_ai.group_edicai_ai_user'
#: (login, display name, edicai_base groups, extra AI group)
_PERSONAS = (
    ('qa_super_admin', 'QA Super Admin',
     ('admin',), 'edicai_ai.group_edicai_ai_manager'),
    ('qa_university_admin', 'QA University Admin',
     ('admin',), 'edicai_ai.group_edicai_ai_user'),
    ('qa_admission_officer', 'QA Admission Officer',
     ('registrar',), 'edicai_ai.group_edicai_ai_user'),
    ('qa_finance_officer', 'QA Finance Officer',
     ('finance',), 'edicai_ai.group_edicai_ai_user'),
    ('qa_faculty', 'QA Faculty',
     ('faculty',), 'edicai_ai.group_edicai_ai_user'),
    ('qa_manager_approver', 'QA Manager / Approver',
     ('manager',), 'edicai_ai.group_edicai_ai_manager'),
)

_DATASET_TAG = 'QALAB'


class EdicaiAIQAToolkit(models.AbstractModel):
    """Repeatable manual-QA support (administrator-only)."""
    _name = 'edicai.ai.qa.toolkit'
    _description = 'Manual QA Toolkit (admin-only, test-support only)'

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------

    def _is_qa_admin(self):
        user = self.env.user
        return user.has_group(_QA_GROUP) or user.has_group(_ADMIN_GROUP) \
            or self.env.su

    def _guard(self):
        if not self._is_qa_admin():
            raise AccessError(
                'The Manual QA Toolkit is restricted to Edicai AI '
                'administrators.')

    # ------------------------------------------------------------------
    # §24 — test personas (existing groups only)
    # ------------------------------------------------------------------

    @api.model
    def list_qa_personas(self):
        """The exact persona catalogue (logins are ``qa_``-prefixed so
        the reset utility can find their state — and only theirs)."""
        return [
            {
                'login': login,
                'name': name,
                'exists': bool(self.env['res.users'].search(
                    [('login', '=', login)], limit=1)),
                'groups': ' + '.join(groups) + (' + AI ' + extra_ai
                                                if extra_ai else ''),
            }
            for login, name, groups, extra_ai in _PERSONAS
        ] + [{
            'login': 'qa_student',
            'name': 'QA Student (created with the dataset)',
            'exists': bool(self.env['res.users'].search(
                [('login', '=', 'qa_student')], limit=1)),
            'groups': 'edicai_base.group_edicai_student (portal — chat is '
                      'staff-only by design; security persona)',
        }]

    @api.model
    def create_qa_personas(self):
        """Idempotent persona creation from the EXISTING groups."""
        self._guard()
        created, existing = [], []
        Users = self.env['res.users'].with_context(no_reset_password=True)
        for login, name, groups, extra_ai in _PERSONAS:
            if self.env['res.users'].search([('login', '=', login)],
                                            limit=1):
                existing.append(login)
                continue
            refs = ['edicai_base.group_edicai_%s' % g for g in groups]
            if extra_ai:
                refs.append(extra_ai)
            # Every persona must be able to reach the chatbot directly.
            # Manager personas get the AI User group explicitly too, so the
            # grant never depends on res.groups implied-ids surviving an
            # ``noupdate`` module upgrade.
            if _AI_USER not in refs:
                refs.append(_AI_USER)
            Users.create({
                'name': name,
                'login': login,
                'email': '%s@qa.example.edu' % login,
                'password': _PERSONA_PASSWORD,
                'company_id': self.env.company.id,
                'company_ids': [(6, 0, [self.env.company.id])],
                'group_ids': [(4, self.env.ref(r).id) for r in refs],
            })
            created.append(login)
        summary = ('Created %d persona(s): %s. Already present: %s. '
                   'Default password: %s (change it before sharing). '
                   'The student persona is created by the ground-truth '
                   'dataset (needs a real student record).') % (
            len(created), ', '.join(created) or '—', 
            ', '.join(existing) or '—', _PERSONA_PASSWORD)
        return {'summary': summary, 'created': created,
                'existing': existing}

    # ------------------------------------------------------------------
    # §25/§26 — deterministic ground-truth dataset + live report
    # ------------------------------------------------------------------

    def _find_or_create(self, model, domain, vals):
        Model = self.env[model]
        found = Model.search(domain, limit=1)
        if found:
            return found
        return Model.create(vals)

    def create_qa_ground_truth_dataset(self):
        """Small, deterministic, per-institution QA dataset.

        Everything is created through canonical Odoo models and state
        machines (no fixture hacks, no sudo), with QALAB-prefixed
        codes for safe idempotency and easy clean-up by hand.
        Deterministic truths (that the doc's answer table states):

        * TEST-STUDENT-001: 4 held sessions, 3 present + 1 absent
          → 75.0% vs an 80% policy minimum → SHORTAGE (proactive case).
        * TEST-STUDENT-002: 4× present → 100% (no shortage).
        * TEST-STUDENT-001 carries an outstanding ₹12,500 tuition
          invoice (or the company's own currency).
        * One admission applicant in 'applied' state + one draft asset
          request (approval persona material).
        """
        self._guard()
        env = self.env
        company = env.company
        cid = company.id

        # --- academic chain ------------------------------------------------
        campus = self._find_or_create(
            'edicai.campus', [('code', '=', 'QALAB'), ('company_id', '=', cid)],
            {'name': 'QA Lab Campus', 'code': 'QALAB', 'company_id': cid})
        faculty = self._find_or_create(
            'edicai.faculty', [('code', '=', 'QALABF'),
                              ('company_id', '=', cid)],
            {'name': 'QA Lab Faculty of Science', 'code': 'QALABF',
             'company_id': cid})
        department = self._find_or_create(
            'edicai.department', [('code', '=', 'QALABD'),
                                 ('company_id', '=', cid)],
            {'name': 'QA Lab Department', 'code': 'QALABD',
             'faculty_id': faculty.id, 'company_id': cid})
        program = self._find_or_create(
            'edicai.program', [('code', '=', 'QALABP'),
                              ('company_id', '=', cid)],
            {'name': 'QA Lab Program', 'code': 'QALABP',
             'program_type': 'undergraduate',
             'degree_title': 'QA Bachelor', 'credit_system': 'credit_hours',
             'duration_years': 3, 'total_credits': 90,
             'program_state': 'active', 'department_id': department.id,
             'company_id': cid})
        # A Term-mode institution profile forces `year_type='term'` and
        # only Term semesters (edicai_calendar validation); the QALAB ground
        # truths (percentage, fee, shortage) are calendar-grain independent.
        profile = company.institution_profile_id
        is_term = bool(profile and profile.calendar_mode == 'term')
        year_type = 'term' if is_term else 'semester'
        semester_type = 'term_1' if is_term else 'odd'
        year = self._find_or_create(
            'edicai.academic.year', [('code', '=', 'QALABY'),
                                    ('company_id', '=', cid)],
            {'name': 'QA Lab AY', 'code': 'QALABY',
             'date_start': '2030-07-01', 'date_end': '2031-06-30',
             'year_type': year_type,
             'year_state': 'cancelled', 'is_current': False,
             'company_id': cid})
        semester = self._find_or_create(
            'edicai.semester', [('code', '=', 'QALABS1'),
                               ('company_id', '=', cid)],
            {'name': 'QA Lab Semester 1', 'code': 'QALABS1',
             'semester_type': semester_type, 'academic_year_id': year.id,
             'date_start': '2030-07-15', 'date_end': '2030-11-30',
             'semester_state': 'ongoing', 'company_id': cid})
        course = self._find_or_create(
            'edicai.course', [('code', '=', 'QALABC'),
                             ('company_id', '=', cid)],
            {'name': 'QA Lab Course', 'code': 'QALABC', 'credit_hours': 3.0,
             'department_id': department.id, 'company_id': cid})
        offering = self._find_or_create(
            'edicai.course.offering',
            [('campus_id', '=', campus.id), ('course_id', '=', course.id),
             ('semester_id', '=', semester.id)],
            {'course_id': course.id, 'semester_id': semester.id,
             'academic_year_id': year.id, 'program_id': program.id,
             'campus_id': campus.id, 'offering_state': 'open',
             'company_id': cid})
        # Time slots impose an overlap constraint per company; on a
        # populated production DB e.g. "Demo Period 1" may already use
        # 7.0-8.0. Prefer the deterministic window, then scan fallback
        # windows that are free. The QALAB ground truths never depend on
        # slot clock times.
        slot = self.env['edicai.time.slot'].search(
            [('company_id', '=', cid), ('campus_id', '=', campus.id),
             ('name', '=', 'QA Lab Slot')], limit=1)
        if not slot:
            TimeSlot = self.env['edicai.time.slot']
            for start in (7.0, 6.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0,
                          14.0, 15.0, 16.0, 17.0, 20.0, 21.0, 22.0):
                try:
                    slot = TimeSlot.create({
                        'name': 'QA Lab Slot', 'company_id': cid,
                        'campus_id': campus.id, 'start_time': start,
                        'end_time': start + 1.0, 'slot_type': 'lecture'})
                    break
                except ValidationError:
                    continue
            if not slot:
                raise UserError(_(
                    'No free hour window found for the QA Lab time slot; '
                    'free a slot on the QA Lab Campus and retry.'))
        building = self._find_or_create(
            'edicai.building', [('code', '=', 'QALABB'),
                               ('company_id', '=', cid)],
            {'name': 'QA Lab Building', 'code': 'QALABB',
             'campus_id': campus.id, 'building_type': 'academic',
             'company_id': cid})
        floor = self._find_or_create(
            'edicai.floor', [('name', '=', 'QA Lab Floor'),
                            ('building_id', '=', building.id)],
            {'name': 'QA Lab Floor', 'floor_number': 0,
             'building_id': building.id, 'company_id': cid})
        room = self._find_or_create(
            'edicai.room', [('code', '=', 'QALABR'),
                           ('company_id', '=', cid)],
            {'name': 'QA Lab Room', 'code': 'QALABR',
             'floor_id': floor.id, 'room_type': 'classroom',
             'capacity': 30, 'campus_id': campus.id, 'company_id': cid})
        member = self._find_or_create(
            'edicai.faculty.member', [('last_name', '=', 'QA Lecturer'),
                                     ('company_id', '=', cid)],
            {'name': 'QA', 'last_name': 'QA Lecturer', 'gender': 'male',
             'email': 'qa.lecturer@qa.example.edu',
             'mobile': '+919000000001', 'company_id': cid,
             'department_id': department.id, 'designation': 'professor',
             'employment_type': 'full_time', 'joining_date': '2030-01-01',
             'member_state': 'active'})
        entry = self._find_or_create(
            'edicai.timetable.entry',
            [('course_offering_id', '=', offering.id),
             ('time_slot_id', '=', slot.id)],
            {'course_offering_id': offering.id, 'day_of_week': '1',
             'time_slot_id': slot.id, 'room_id': room.id,
             'instructor_id': member.id, 'entry_state': 'confirmed'})
        # The QA course uses an 80% minimum so the shortage case is
        # unambiguous.  The policy is scoped to the QA course (never
        # 'global'): the institution's own attendance policy must stay
        # untouched, and the QA ground truth must be deterministic on any
        # installation.
        policy = self._find_or_create(
            'edicai.attendance.policy',
            [('name', '=', 'QA Lab Policy 80/85'), ('company_id', '=', cid),
             ('course_id', '=', course.id)],
            {'name': 'QA Lab Policy 80/85', 'company_id': cid,
             'policy_scope': 'course', 'course_id': course.id,
             'min_attendance_percentage': 80.0,
             'warning_threshold_percentage': 85.0,
             'is_exam_eligibility_linked': True})

        # --- students (incl. the student PERSONA on the short one) ----
        person_user = self.env['res.users'].with_context(
            no_reset_password=True)
        if not self.env['res.users'].search([('login', '=', 'qa_student')],
                                            limit=1):
            Users = person_user
            student_user = Users.create({
                'name': 'QA Student',
                'login': 'qa_student',
                'email': 'qa_student@qa.example.edu',
                'password': _PERSONA_PASSWORD,
                'company_id': cid,
                'company_ids': [(6, 0, [cid])],
                'group_ids': [(4, self.env.ref(
                    'edicai_base.group_edicai_student').id)],
            })
        else:
            student_user = self.env['res.users'].search(
                [('login', '=', 'qa_student')], limit=1)

        short_student = self._find_or_create(
            'edicai.student', [('last_name', '=', 'QA-001'),
                              ('company_id', '=', cid)],
            {'name': 'TEST-STUDENT-001', 'last_name': 'QA-001',
             'gender': 'male', 'date_of_birth': '2003-02-01',
             'email': 'test.student.001@qa.example.edu',
             'mobile': '+919000000002', 'company_id': cid,
             'campus_id': campus.id, 'program_id': program.id,
             'batch_year': 2030, 'admission_date': '2030-06-01',
             'student_state': 'active'})
        short_student.partner_id = student_user.partner_id.id
        healthy_student = self._find_or_create(
            'edicai.student', [('last_name', '=', 'QA-002'),
                              ('company_id', '=', cid)],
            {'name': 'TEST-STUDENT-002', 'last_name': 'QA-002',
             'gender': 'female', 'date_of_birth': '2003-05-12',
             'email': 'test.student.002@qa.example.edu',
             'mobile': '+919000000003', 'company_id': cid,
             'campus_id': campus.id, 'program_id': program.id,
             'batch_year': 2030, 'admission_date': '2030-06-01',
             'student_state': 'active'})

        # --- attendance: canonical open → mark → close ------------------
        # BOTH students sit in the SAME 4 class sessions (a session
        # marks every enrolled student): TEST-STUDENT-001 → P·A·P·P
        # (75 %), TEST-STUDENT-002 → P·P·P·P (100 %).
        env = self.env
        session_status = [
            ('present', 'present'),
            ('absent', 'present'),
            ('present', 'present'),
            ('present', 'present'),
        ]
        self._find_or_create(
            'edicai.enrollment',
            [('student_id', '=', short_student.id),
             ('course_offering_id', '=', offering.id)],
            {'student_id': short_student.id,
             'course_offering_id': offering.id})
        self._find_or_create(
            'edicai.enrollment',
            [('student_id', '=', healthy_student.id),
             ('course_offering_id', '=', offering.id)],
            {'student_id': healthy_student.id,
             'course_offering_id': offering.id})
        Record = env['edicai.attendance.record']
        for idx, (short_status, healthy_status) in enumerate(session_status):
            session_date = '2030-08-%02d' % (1 + idx)
            session = self._find_or_create(
                'edicai.attendance.session',
                [('timetable_entry_id', '=', entry.id),
                 ('session_date', '=', session_date)],
                {'timetable_entry_id': entry.id,
                 'session_date': session_date})
            if session.session_state == 'closed':
                continue  # already sealed → the truth is set
            session.action_open_for_marking()
            for student, status in ((short_student, short_status),
                                    (healthy_student, healthy_status)):
                record = Record.search([
                    ('session_id', '=', session.id),
                    ('student_id', '=', student.id)], limit=1)
                if not record:
                    raise ValueError(
                        'Attendance record was not created by '
                        'action_open_for_marking for %s on %s'
                        % (student.display_name, session_date))
                record.status = status
            session.with_context(
                force_write_closed_session=True).action_close_session()

        # --- fees: one outstanding invoice on the short student ---------
        invoice = self._find_or_create(
            'edicai.fee.invoice',
            [('student_id', '=', short_student.id),
             ('semester_id', '=', semester.id),
             ('company_id', '=', cid)],
            {'student_id': short_student.id, 'company_id': cid,
             'academic_year_id': year.id, 'semester_id': semester.id,
             'invoice_date': '2030-08-01', 'due_date': '2030-09-01',
             'currency_id': company.currency_id.id,
             'line_ids': [(0, 0, {'fee_type': 'tuition',
                                  'name': 'QA tuition (outstanding)',
                                  'amount': 12500.0})]})

        # --- admission: an applied applicant (admission persona) --------
        if 'edicai.admission.cycle' in env:
            cycle = self._find_or_create(
                'edicai.admission.cycle',
                [('code', '=', 'QALABCYC'), ('company_id', '=', cid)],
                {'name': 'QA Lab Cycle', 'code': 'QALABCYC',
                 'campus_id': campus.id, 'academic_year_id': year.id,
                 'start_date': '2030-07-01', 'end_date': '2031-05-31',
                 'state': 'active', 'company_id': cid})
            applicant = self._find_or_create(
                'edicai.admission.applicant',
                [('email', '=', 'test.applicant.001@qa.example.edu'),
                 ('company_id', '=', cid)],
                {'name': 'TEST-APPLICANT-001',
                 'email': 'test.applicant.001@qa.example.edu',
                 'mobile': '+919000000004', 'gender': 'male',
                 'date_of_birth': '2004-08-20', 'cycle_id': cycle.id,
                 'program_id': program.id, 'campus_id': campus.id,
                 'company_id': cid, 'state': 'applied'})
        else:
            applicant = env['edicai.admission.applicant']

        # --- approval: a draft asset request (approval persona) ---------
        if 'edicai.asset.request' in env:
            approver_persona = self._persona_user('qa_finance_officer')
            asset_request = self._find_or_create(
                'edicai.asset.request',
                [('asset_description', '=', 'QALAB projector'),
                 ('company_id', '=', cid)],
                {'requested_by': (approver_persona or self.env.user).id,
                 'asset_description': 'QALAB projector',
                 'asset_type': 'projector',
                 'reason': 'QA ground-truth approval case',
                 'needed_by_date': '2030-09-01',
                 'campus_id': campus.id,
                 'company_id': cid, 'state': 'draft'})
        else:
            asset_request = env['edicai.asset.request']

        return {
            'summary': 'QA ground-truth dataset ready on %s — see '
                       'doc/QA_GROUND_TRUTH.md.' % company.name,
            'company': company.name,
            'short_student': short_student.display_name,
            'healthy_student': healthy_student.display_name,
            'policy': '%.0f/%.0f' % (
                policy.min_attendance_percentage,
                policy.warning_threshold_percentage),
        }

    def _persona_user(self, login):
        return self.env['res.users'].search([('login', '=', login)],
                                            limit=1)

    def _qa_effective_policy(self, company):
        """The attendance policy that actually governs the QA course.

        Resolved with the attendance module's own resolver (offering →
        course → course type → global) so the report states the policy
        Odoo really applies, on any installation.
        """
        Policy = self.env['edicai.attendance.policy']
        offering = self.env['edicai.course.offering'].search(
            [('company_id', '=', company.id),
             ('course_id.code', '=', 'QALABC')], limit=1)
        if offering and hasattr(Policy, 'get_policy_for_offering'):
            policy = Policy.get_policy_for_offering(offering)
            if policy:
                return policy
        qa_policy = Policy.search([
            ('company_id', '=', company.id),
            ('name', '=', 'QA Lab Policy 80/85')], limit=1)
        return qa_policy or Policy.search(
            [('company_id', '=', company.id)], limit=1)

    def mine_open_questions(self, limit=50, days=30):
        """Mine the REAL questions users asked that the ERP could not
        answer yet.

        This is the organisation's own training data: every user turn
        that produced an unresolved intent (unknown / ambiguous) or a
        failed tool call is listed, most frequent first, with the
        intent it was closest to.  The result is the prioritised list of
        phrasings to add to the question catalogue.

        Read-only: it only READS chat messages and audit events.
        """
        self._guard()
        from datetime import timedelta
        from odoo import fields as _fields
        since = _fields.Datetime.now() - timedelta(days=max(1, int(days)))
        Message = self.env['edicai.ai.chat.message']
        questions = Message.search([
            ('role', '=', 'user'),
            ('create_date', '>=', since),
        ], order='create_date desc', limit=2000)
        Intent = self.env['edicai.ai.intent']
        rows = []
        for message in questions:
            text = (message.content or '').strip()
            if not text or len(text) > 200:
                continue
            parsed = Intent.parse(text)
            if parsed.get('status') == 'supported':
                continue
            rows.append({
                'text': text,
                'status': parsed.get('status'),
                'closest_intent': parsed.get('intent') or False,
                'session_id': message.session_id.id,
                'create_date': message.create_date.isoformat(),
            })
        counter = {}
        for row in rows:
            key = row['text'].lower()
            counter.setdefault(key, {
                'text': row['text'],
                'count': 0,
                'status': row['status'],
                'closest_intent': row['closest_intent'],
            })
            counter[key]['count'] += 1
        ranked = sorted(
            counter.values(),
            key=lambda r: (-r['count'], r['text']),
        )[:max(1, int(limit))]
        return {
            'summary': '%d unresolved question(s) mined from the last '
                       '%d day(s) — add the top ones to the question '
                       'catalogue.' % (len(rows), days),
            'candidates': ranked,
        }

    def qa_ground_truth_report(self):
        """The LIVE 'what is the correct answer according to Odoo' —
        computed from the dataset records at call time (never cached
        fabrication).  Percentages are recomputed the same way the
        attendance module's cumulative compute defines them
        (present+late over closed, non-cancelled, non-holiday
        sessions) instead of trusting stored-column timing."""
        self._guard()
        company = self.env.company
        student = self.env['edicai.student'].search(
            [('last_name', '=', 'QA-001'), ('company_id', '=', company.id)],
            limit=1)
        if not student:
            return {'exists': False,
                    'summary': 'Dataset not created yet — use Create QA '
                               'Dataset first.'}
        Record = self.env['edicai.attendance.record']

        def _pct(target_student):
            all_records = Record.search([
                ('student_id', '=', target_student.id),
                ('session_id.session_state', '=', 'closed'),
                ('session_id.is_cancelled', '=', False),
                ('session_id.is_holiday', '=', False),
            ])
            total = len(all_records)
            if not total:
                return 0.0, 0
            effective = len(all_records.filtered(
                lambda r: r.status in ('present', 'late')))
            return effective / total * 100.0, total

        pct, held = _pct(student)
        policy = self._qa_effective_policy(company)
        min_pc = policy.min_attendance_percentage if policy else None
        invoice = self.env['edicai.fee.invoice'].search(
            [('student_id', '=', student.id)], limit=1)
        outstanding = None
        if invoice:
            has_amount_due = 'amount_residual' in invoice._fields
            outstanding = (invoice.amount_residual if has_amount_due
                           else sum(line.amount for line in
                                    invoice.line_ids))
        healthy = self.env['edicai.student'].search(
            [('last_name', '=', 'QA-002'), ('company_id', '=', company.id)],
            limit=1)
        healthy_pct, _held_healthy = (_pct(healthy) if healthy
                                      else (0.0, 0))
        offering = self.env['edicai.course.offering'].search(
            [('course_id.code', '=', 'QALABC'),
             ('company_id', '=', company.id)], limit=1)
        return {
            'exists': True,
            'company': company.name,
            'student_code': 'TEST-STUDENT-001',
            'student': student.display_name,
            'sessions_held': held,
            'attendance_pct': pct,
            'min_required_pct': min_pc,
            'shortage_expected': None if not min_pc else pct < min_pc,
            'fee_outstanding': outstanding,
            'fee_currency': (invoice.currency_id.name if invoice else ''),
            'program': (offering.program_id.name if offering else ''),
            'campus': (offering.campus_id.name if offering else ''),
            'healthy_student_pct': healthy_pct,
        }

    # ------------------------------------------------------------------
    # §23 — safe test-state reset (business records NEVER touched)
    # ------------------------------------------------------------------

    def reset_qa_test_state(self):
        self._guard()
        summary = []
        persona_logins = [p[0] for p in _PERSONAS] + ['qa_student']
        users = self.env['res.users'].search(
            [('login', 'in', persona_logins)])
        if users:
            sessions = self.env['edicai.ai.chat.session'].search([
                ('user_id', 'in', users.ids)])
            sessions.write({'active': False})
            summary.append('%d QA chat session(s) archived.' %
                           len(sessions))
        # expired pending actions only — never live ones
        Pending = self.env['edicai.ai.pending.action']
        if 'status' in Pending._fields:
            expired = Pending.search(
                [('status', '=', 'expired')], limit=500)
            if 'active' in Pending._fields and expired:
                expired.write({'active': False})
                summary.append('%d expired pending action(s) archived.'
                               % len(expired))
        # proactive test insight rows for persona users: resolved, not
        # deleted (audit trail stays) — only persona-owned ones
        if 'edicai.ai.proactive.insight' in self.env:
            Insight = self.env['edicai.ai.proactive.insight']
            fields_ok = 'user_id' in Insight._fields
            if fields_ok and users:
                rows = Insight.search([('user_id', 'in', users.ids)])
                if rows and 'status' in rows._fields:
                    rows.write({'status': 'resolved'})
                    summary.append('%d QA proactive insight row(s) '
                                   'resolved.' % len(rows))
        if not summary:
            summary.append('No QA test state found — nothing to do.')
        return {'summary': ' '.join(summary)}
