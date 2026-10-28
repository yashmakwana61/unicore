"""Phase G3 tests — declared record actions behind the confirm flow.

Guarantees under test:

* staging NEVER executes: a proposal only validates (entity execute
  grant, action row + groups, CODE registry, closed params, readable
  record) and stages ONE pending action;
* TWO independent gates, both deny-by-default: the DATA gate
  (``edicai.ai.entity.action`` row + ``execute_groups`` + master flag)
  and the CODE gate (``ai_entity_actions.ENTITY_ACTIONS``). A data row
  naming ``write``/``unlink``/``sudo``/``create`` is dead data and is
  refused with no side effect;
* approval-required rows are REFUSED (never silently treated as
  approved);
* execution happens ONLY in ``confirm_and_execute`` — locked, exactly
  once, as the CONFIRMING user, through the ERP's own method (no sudo,
  no invented field writes), verified by re-reading the declared state
  column;
* a business rejection (UserError/ValidationError) keeps the row
  retryable (draft); an ACL denial is a sanitized ``denied``;
* revoking the grant or the flag between preview and confirm DENIES.
"""

import base64

import odoo.tests
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_entity_actions import ENTITY_ACTIONS
from odoo.addons.edicai_ai.models.ai_pending_action import (
    ACTION_ENTITY_EXECUTE,
    STATUS_DRAFT,
    STATUS_EXECUTED,
    STATUS_PREVIEW,
)
from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures

EXECUTE_FLAG = 'edicai_ai.action_entity_execute_enabled'
WRITE_FLAG = 'edicai_ai.action_entity_write_enabled'

AI_GROUP = 'edicai_ai.group_edicai_ai_user'


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIEntityActionTest(TransactionCase, Phase1AFixtures):
    """entity.execute — declared methods, preview → confirm → verified."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_academic_core(suffix='GXA')

        Policy = cls.env['edicai.ai.entity.policy']
        for model_ref, label, ops in (
                ('edicai.student', 'Students',
                 'search,read,aggregate,describe,list'),
                ('edicai.student.document', 'Student Documents', 'execute'),
                ('edicai.admission.applicant', 'Admission Applicants',
                 'search,read,aggregate,describe,list')):
            if not Policy.search([('model_ref', '=', model_ref)]):
                Policy.create({
                    'model_ref': model_ref,
                    'label': label,
                    'read_groups': AI_GROUP if ops != 'execute' else False,
                    'ops': ops,
                    'max_rows': 100,
                })

        # The data gate (as seeded). Defensive creation keeps the tests
        # independent of whether the seed already ran in this database.
        Action = cls.env['edicai.ai.entity.action'].sudo()
        for model_ref, action, label in (
                ('edicai.student', 'action_activate',
                 'Activate student'),
                ('edicai.student.document', 'action_verify',
                 'Verify document'),
                ('edicai.student.document', 'action_unverify',
                 'Unverify document'),
                ('edicai.admission.applicant', 'action_move_to_waitlist',
                 'Move to waitlist')):
            row = Action.search([
                ('model_ref', '=', model_ref),
                ('action', '=', action)], limit=1)
            if not row:
                Action.create({
                    'model_ref': model_ref,
                    'action': action,
                    'label': label,
                    'allowed_groups': AI_GROUP,
                    'needs_approval': False,
                    'enabled': True,
                })

        cls.mgr = cls._create_staff_user(
            login_suffix='g3mgr', groups=('manager',))
        cls.staff = cls._create_staff_user(login_suffix='g3staff')
        cls.tools = cls.env['edicai.ai.entity.tools'].with_user(cls.mgr)
        cls.staff_tools = cls.env['edicai.ai.entity.tools'].with_user(
            cls.staff)
        cls.session = cls.env['edicai.ai.chat.session'].with_user(
            cls.mgr).create({'title': 'G3 actions'})
        cls.staff_session = cls.env['edicai.ai.chat.session'].with_user(
            cls.staff).create({'title': 'G3 staff session'})
        cls.Pending = cls.env['edicai.ai.pending.action']

        cls.student, cls.student_user = cls._create_student(
            login_suffix='g3s1', name='Kabir', last_name='Action')
        # A non-active student WITH a current semester: action_activate
        # is a legal transition for it.
        cls.leave_student, _portal = cls._create_student(
            login_suffix='g3s2', name='Meera', last_name='Leave')
        cls.leave_student.write({
            'student_state': 'on_leave',
            'current_semester_id': cls.semester.id,
        })
        cls.doc = cls.env['edicai.student.document'].create({
            'name': 'G3 Passport Scan',
            'document_type': 'passport',
            'file': base64.b64encode(b'g3-document'),
            'file_name': 'passport.pdf',
            'student_id': cls.student.id,
        })
        cls.cycle = cls.env['edicai.admission.cycle'].create({
            'name': 'G3 Cycle',
            'code': 'G3C',
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2030-01-01',
            'end_date': '2030-06-30',
            'company_id': cls.company.id,
        })

    # -- helpers --------------------------------------------------------

    @classmethod
    def _policy(cls, model):
        return cls.env['edicai.ai.entity.policy'].search(
            [('model_ref', '=', model)], limit=1)

    @classmethod
    def _grant(cls, model='edicai.student.document', groups=AI_GROUP):
        policy = cls._policy(model)
        ops = set(policy._ops_list()) | {'execute'}
        policy.write({
            'ops': ','.join(sorted(ops)),
            'execute_groups': groups,
        })
        cls.env['ir.config_parameter'].set_param(EXECUTE_FLAG, 'True')

    @classmethod
    def _revoke(cls, model='edicai.student.document'):
        cls._policy(model).write({'execute_groups': ''})

    def _make_applicant(self, state='shortlisted'):
        return self.env['edicai.admission.applicant'].create({
            'name': 'G3 Applicant',
            'email': 'g3.applicant@test.edu',
            'mobile': '919800001234',
            'gender': 'male',
            'date_of_birth': '2004-03-15',
            'cycle_id': self.cycle.id,
            'program_id': self.program.id,
            'campus_id': self.campus.id,
            'company_id': self.company.id,
            'state': state,
        })

    def _stage(self, action='action_verify',
               model='edicai.student.document', record_id=None,
               params=None, session=None, tools=None):
        # NB: a raw model accessor is an EMPTY (falsy) recordset — pick
        # by identity, never with ``or``.
        runner = self.tools if tools is None else tools
        return runner.tool_entity_execute({
            'session_id': (session or self.session).id,
            'model': model,
            'action': action,
            'record_id': record_id if record_id is not None
            else self.doc.id,
            'params': params or {},
        })

    def _pending(self, reply, user=None):
        return self.env['edicai.ai.pending.action'].with_user(
            user or self.mgr).browse(reply['pending_id'])

    def _fresh(self, record):
        fresh = record.browse(record.id)
        fresh.invalidate_recordset()
        return fresh

    # -- 01..03 the DATA gate -------------------------------------------

    def test_01_staging_denied_without_execute_op(self):
        # the seeded student policy does NOT list ``execute``: no op =
        # no action, even for a declared method with an open row.
        with self.assertRaises(UserError):
            self._stage(
                action='action_activate', model='edicai.student',
                record_id=self.leave_student.id)
        self.assertEqual(
            self.Pending.search_count([
                ('action', '=', ACTION_ENTITY_EXECUTE)]), 0)
        self.assertEqual(self._fresh(self.leave_student).student_state,
                         'on_leave')

    def test_02_staging_denied_with_empty_execute_groups(self):
        self._grant()
        self._revoke()
        with self.assertRaises(UserError):
            self._stage()
        self.assertEqual(
            self.Pending.search_count([
                ('action', '=', ACTION_ENTITY_EXECUTE)]), 0)

    def test_03_staging_denied_when_action_row_closed_or_unknown(self):
        self._grant()
        row = self.env['edicai.ai.entity.action'].sudo().search([
            ('model_ref', '=', 'edicai.student.document'),
            ('action', '=', 'action_verify')], limit=1)
        row.enabled = False
        with self.assertRaises(UserError):
            self._stage()
        row.enabled = True
        with self.assertRaises(UserError):
            self._stage(action='action_not_declared')
        self.assertFalse(self._fresh(self.doc).is_verified)

    # -- 04 the CODE gate (belt + braces) -------------------------------

    def test_04_undeclared_methods_are_structurally_refused(self):
        """A DATA row can never widen the CODE registry."""
        self._grant('edicai.student')
        Action = self.env['edicai.ai.entity.action'].sudo()
        attack = ('write', 'unlink', 'sudo', 'create', 'search')
        for name in attack:
            self.assertNotIn(('edicai.student', name), ENTITY_ACTIONS)
            Action.create({
                'model_ref': 'edicai.student',
                'action': name,
                'label': name,
                'allowed_groups': AI_GROUP,
                'needs_approval': False,
                'enabled': True,
            })
        before = self._fresh(self.student)
        for name in attack:
            with self.assertRaises(UserError):
                self._stage(
                    action=name, model='edicai.student',
                    record_id=self.student.id)
        after = self._fresh(self.student)
        self.assertEqual(after.name, before.name)
        self.assertEqual(after.student_state, before.student_state)
        self.assertEqual(
            self.Pending.search_count([
                ('action', '=', ACTION_ENTITY_EXECUTE)]), 0)

    # -- 05 approval-required rows are refused --------------------------

    def test_05_approval_required_action_is_refused(self):
        self._grant()
        row = self.env['edicai.ai.entity.action'].sudo().search([
            ('model_ref', '=', 'edicai.student.document'),
            ('action', '=', 'action_verify')], limit=1)
        row.needs_approval = True
        with self.assertRaises(UserError) as caught:
            self._stage()
        self.assertIn('approval', str(caught.exception).lower())
        self.assertEqual(
            self.Pending.search_count([
                ('action', '=', ACTION_ENTITY_EXECUTE)]), 0)
        self.assertFalse(self._fresh(self.doc).is_verified)

    # -- 06..09 the lifecycle -------------------------------------------

    def test_06_staging_never_executes(self):
        self._grant()
        reply = self._stage(params={'note': 'Checked against original'})
        self.assertTrue(reply['requires_confirmation'])
        self.assertEqual(reply['status'], STATUS_PREVIEW)
        self.assertEqual(reply['entity_action'], 'action_verify')
        self.assertFalse(reply['superseded'])
        row = self._pending(reply)
        self.assertEqual(row.action, ACTION_ENTITY_EXECUTE)
        self.assertTrue(row.ref)
        payload = row._read_payload()
        self.assertEqual(payload['model'], 'edicai.student.document')
        self.assertEqual(payload['entity_action'], 'action_verify')
        self.assertEqual(payload['record_id'], self.doc.id)
        self.assertEqual(payload['params'],
                         {'note': 'Checked against original'})
        # no write happened at staging
        self.assertFalse(self._fresh(self.doc).is_verified)

    def test_07_confirm_verifies_document_as_the_caller(self):
        self._grant()
        reply = self._stage(params={'note': 'Seen and checked'})
        row = self._pending(reply)
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')
        verified = outcome['verified']
        self.assertEqual(verified['id'], self.doc.id)
        self.assertEqual(verified['action_label'], 'Verify document')
        self.assertTrue(verified['changed'])
        self.assertFalse(verified['state_before'])
        self.assertTrue(verified['state_after'])
        doc = self._fresh(self.doc)
        self.assertTrue(doc.is_verified)
        self.assertEqual(doc.verified_by.id, self.mgr.id)
        self.assertEqual(doc.verification_notes, 'Seen and checked')
        self.assertEqual(row.status, STATUS_EXECUTED)
        self.assertEqual(row.result_res_id, self.doc.id)

    def test_08_already_in_state_is_a_clean_noop(self):
        self._grant()
        self.doc.with_user(self.mgr).action_verify()
        stamped = self._fresh(self.doc).verified_on
        reply = self._stage()
        outcome = self._pending(reply).with_user(
            self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')
        self.assertFalse(outcome['verified']['changed'])
        # the ERP method was NOT called again (timestamp untouched)
        self.assertEqual(self._fresh(self.doc).verified_on, stamped)

    def test_09_second_confirmation_is_idempotent(self):
        self._grant()
        reply = self._stage()
        row = self._pending(reply)
        self.assertEqual(
            row.with_user(self.mgr).confirm_and_execute()['outcome'],
            'executed')
        events = self.env['edicai.ai.audit.event'].sudo().search_count([
            ('event_type', '=', 'ACTION_EXECUTED'),
            ('reason_code', '=', 'ENTITY_EXECUTE'),
            ('tool_name', '=', 'entity.execute'),
        ])
        doubled = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(doubled['outcome'], 'not_confirmable')
        self.assertEqual(
            self.env['edicai.ai.audit.event'].sudo().search_count([
                ('event_type', '=', 'ACTION_EXECUTED'),
                ('reason_code', '=', 'ENTITY_EXECUTE'),
                ('tool_name', '=', 'entity.execute'),
            ]), events)

    # -- 10 business rejection keeps the row retryable -------------------

    def test_10_business_rule_at_execution_is_retryable(self):
        """The ERP state machine stays authoritative."""
        self._grant('edicai.admission.applicant')
        applicant = self._make_applicant(state='inquiry')
        reply = self._stage(
            action='action_move_to_waitlist',
            model='edicai.admission.applicant',
            record_id=applicant.id)
        row = self._pending(reply)
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'error')
        self.assertEqual(outcome['error_code'], 'VALIDATION_FAILED')
        self.assertEqual(
            self._fresh(applicant).state, 'inquiry')
        fresh = self.Pending.browse(row.id)
        fresh.invalidate_recordset()
        self.assertEqual(fresh.status, STATUS_DRAFT)
        self.assertEqual(fresh.failure_reason, 'VALIDATION_FAILED')
        event = self.env['edicai.ai.audit.event'].sudo().search([
            ('event_type', '=', 'ACTION_ERROR'),
            ('reason_code', '=', 'VALIDATION_FAILED'),
            ('tool_name', '=', 'entity.execute'),
        ], order='id desc', limit=1)
        self.assertTrue(event)
        self.assertEqual(
            event.metadata_json.get('exception_type'), 'UserError')

    # -- 11..12 re-authorization at confirm time ------------------------

    def test_11_confirm_denied_when_grant_revoked(self):
        self._grant()
        reply = self._stage()
        self._revoke()
        row = self._pending(reply)
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(outcome['reason_code'], 'ENTITY_EXECUTE_GROUPS')
        self.assertEqual(row.status, STATUS_PREVIEW)
        self.assertFalse(self._fresh(self.doc).is_verified)
        # re-grant + confirm now executes
        self._grant()
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')
        self.assertTrue(self._fresh(self.doc).is_verified)

    def test_12_confirm_denied_when_master_flag_off(self):
        self._grant()
        reply = self._stage()
        self.env['ir.config_parameter'].set_param(EXECUTE_FLAG, 'False')
        row = self._pending(reply)
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(outcome['reason_code'], 'ENTITY_EXECUTE_DISABLED')
        self.assertEqual(row.status, STATUS_PREVIEW)
        self.assertFalse(self._fresh(self.doc).is_verified)

    # -- 13..15 identity, existence, ACL --------------------------------

    def test_13_other_users_session_rejected(self):
        self._grant()
        with self.assertRaises(UserError):
            self._stage(session=self.staff_session)

    def test_14_ghost_record_rejected_at_staging(self):
        self._grant()
        with self.assertRaises(UserError):
            self._stage(record_id=self.doc.id + 999999)
        self.assertEqual(
            self.Pending.search_count([
                ('action', '=', ACTION_ENTITY_EXECUTE)]), 0)

    def test_15_acl_denial_is_never_bypassed(self):
        """No sudo: a caller who may READ but not WRITE is denied by the
        ERP method itself, and nothing changes."""
        self._grant()
        reply = self._stage(tools=self.staff_tools,
                            session=self.staff_session)
        row = self._pending(reply, user=self.staff)
        outcome = row.with_user(self.staff).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(outcome['reason_code'],
                         'ACL_DENIED_AT_EXECUTION')
        self.assertEqual(row.status, STATUS_PREVIEW)
        doc = self._fresh(self.doc)
        self.assertFalse(doc.is_verified)
        self.assertFalse(doc.verification_notes)

    # -- 16 list_actions tells the truth per caller ---------------------

    def test_16_list_actions_marks_executable_per_caller(self):
        self._grant('edicai.student.document')
        reply = self.tools.tool_list_actions(
            {'model': 'edicai.student.document'})
        by_action = {item['action']: item for item in reply['actions']}
        self.assertIn('action_verify', by_action)
        self.assertTrue(by_action['action_verify']['executable'])
        self.assertEqual(by_action['action_verify']['reason_code'], 'OK')
        self.assertEqual(by_action['action_verify']['label'],
                         'Verify document')
        # applicant actions are listed but NOT executable (no grant)
        other = self.tools.tool_list_actions(
            {'model': 'edicai.admission.applicant'})
        self.assertTrue(other['actions'])
        for item in other['actions']:
            self.assertFalse(item['executable'])
            self.assertEqual(item['reason_code'], 'ENTITY_UNKNOWN')

    # -- 17 closed parameter grammar ------------------------------------

    def test_17_parameter_grammar_is_closed(self):
        self._grant()
        for params in ({'target': 'x'},
                       {'note': 42},
                       {'note': 'x' * 501}):
            with self.assertRaises(UserError):
                self._stage(params=params)
        self.assertEqual(
            self.Pending.search_count([
                ('action', '=', ACTION_ENTITY_EXECUTE)]), 0)
        reply = self._stage(params={'note': '  ok  '})
        self.assertEqual(
            self._pending(reply)._read_payload()['params'],
            {'note': 'ok'})

    # -- 18 the durable audit trail -------------------------------------

    def test_18_audit_trail_is_durable_and_payload_free(self):
        self._grant()
        reply = self._stage(params={'note': 'secret-note-text'})
        self._pending(reply).with_user(self.mgr).confirm_and_execute()
        Audit = self.env['edicai.ai.audit.event'].sudo()
        events = Audit.search([
            ('tool_name', '=', 'entity.execute'),
        ], order='id')
        kinds = [event.event_type for event in events]
        self.assertIn('ACTION_PREVIEW_CREATED', kinds)
        self.assertIn('ACTION_CONFIRMED', kinds)
        self.assertIn('ACTION_EXECUTED', kinds)
        executed = events.filtered(
            lambda e: e.event_type == 'ACTION_EXECUTED')
        self.assertEqual(executed.reason_code, 'ENTITY_EXECUTE')
        # no note text (or any payload) leaked into the audit metadata
        for event in events:
            blob = str(event.metadata_json or '')
            self.assertNotIn('secret-note-text', blob)

    # -- 19..20 the conversational lane ---------------------------------

    def test_19_chat_confirmation_executes_the_declared_action(self):
        """The lane opens with the G3 flag ALONE (the G2 write flag
        stays off): record actions are independent."""
        self._grant()
        self.assertFalse(self.env['ir.config_parameter'].get_param(
            WRITE_FLAG, default=False))
        reply = self._stage()
        orchestrator = self.env['edicai.ai.action.orchestrator'].with_user(
            self.mgr)
        result = orchestrator.handle_turn(
            'confirm %s' % reply['pending_ref'], session=self.session)
        self.assertTrue(result, 'the entity lane must answer the turn')
        self.assertIn('Verify document', result['reply'])
        self.assertTrue(self._fresh(self.doc).is_verified)

    def test_20_entity_lane_stays_closed_while_the_flag_is_off(self):
        self._grant()
        reply = self._stage()
        self.env['ir.config_parameter'].set_param(EXECUTE_FLAG, 'False')
        orchestrator = self.env['edicai.ai.action.orchestrator'].with_user(
            self.mgr)
        result = orchestrator.handle_turn(
            'confirm %s' % reply['pending_ref'], session=self.session)
        self.assertFalse(result)
        self.assertFalse(self._fresh(self.doc).is_verified)
