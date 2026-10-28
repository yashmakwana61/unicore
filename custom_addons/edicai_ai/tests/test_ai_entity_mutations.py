"""Phase G2 tests — generic CREATE/UPDATE behind the confirm flow.

Guarantees under test (mirror of Phase 2A/2B, generalized):

* staging tools NEVER write business data — they only produce one
  pending action (preview) after the entity-policy write grant,
  writable-field, type and required checks all pass;
* deny-by-default: empty ``write_groups`` / missing op in ``ops`` /
  foreign model / unknown field / readonly-or-computed field /
  identity+company fields / other-user session all rejected;
* execution happens ONLY in ``confirm_and_execute`` — locked, exactly
  once, as the CONFIRMING user (no sudo; ACL/record rules re-enforced
  by the ORM), verified by a re-read;
* revoking the entity-policy grant or the master flag between preview
  and confirm DENIES the execution (row stays previewable, retryable).
"""

import odoo.tests
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_pending_action import (
    ACTION_ENTITY_CREATE,
    STATUS_DRAFT,
    STATUS_EXECUTED,
    STATUS_PREVIEW,
    STATUS_SUPERSEDED,
)
from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures

ENTITY_FLAG = 'edicai_ai.action_entity_write_enabled'


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIEntityMutationTest(TransactionCase, Phase1AFixtures):
    """entity.create / entity.update proposal + locked execution."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_academic_core(suffix='GMU')
        Policy = cls.env['edicai.ai.entity.policy']
        if not Policy.search([('model_ref', '=', 'edicai.student')]):
            Policy.create({
                'model_ref': 'edicai.student',
                'label': 'Students',
                'read_groups': 'edicai_ai.group_edicai_ai_user',
                'pii_fields': 'mobile',
                'ops': 'search,read,aggregate,describe,list',
                'max_rows': 100,
            })
        cls.entity = Policy.search(
            [('model_ref', '=', 'edicai.student')], limit=1)
        cls.student_a, cls.user_a = cls._create_student(
            login_suffix='g2ma', name='Aarav', last_name='Mutant')
        cls.student_b, cls.user_b = cls._create_student(
            login_suffix='g2mb', name='Diya', last_name='Mutant')

        cls.staff = cls._create_staff_user(login_suffix='g2staff')
        # ERP write ACLs live in a DIFFERENT role layer than the AI
        # policy: fixture 'staff' is read-only on edicai.student, so the
        # mutation flows run under a manager (whose ROLE grants the
        # write ACL; the entity policy grants remain column-scoped).
        cls.mgr = cls._create_staff_user(
            login_suffix='g2mgr', groups=('manager',))
        cls.staff_tools = cls.env['edicai.ai.entity.tools'].with_user(
            cls.staff)
        cls.tools = cls.env['edicai.ai.entity.tools'].with_user(cls.mgr)
        cls.session = cls.env['edicai.ai.chat.session'].with_user(
            cls.mgr).create({'title': 'G2 mutations'})
        cls.staff_session = cls.env['edicai.ai.chat.session'].with_user(
            cls.staff).create({'title': 'G2 staff session'})
        cls.Pending = cls.env['edicai.ai.pending.action']

    # -- grant helpers --------------------------------------------------

    @classmethod
    def _grant_writes(cls):
        cls.entity.write({
            'ops': 'search,read,aggregate,describe,list,create,update',
            'write_groups': 'edicai_ai.group_edicai_ai_user',
        })
        cls.env['ir.config_parameter'].set_param(ENTITY_FLAG, 'True')

    @classmethod
    def _revoke_writes(cls):
        cls.entity.write({'write_groups': ''})

    def _stage_create(self, **overrides):
        values = {
            'name': 'G2 Created Student',
            'gender': 'male',
            'date_of_birth': '2008-05-01',
            'email': 'g2.created@example.com',
            'mobile': '+919890010999',
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'batch_year': 2030,
        }
        values.update(overrides.pop('values_patch', {}) or {})
        params = {
            'session_id': self.session.id,
            'model': 'edicai.student',
            'values': values,
        }
        params.update(overrides)
        return self.tools.tool_entity_create(params)

    def _stage_update(self, record, values, **overrides):
        reply = self.tools.tool_entity_update({
            'session_id': self.session.id,
            'model': 'edicai.student',
            'record_id': record.id,
            'values': values,
        })
        return reply

    def _pending(self, reply):
        return self.env['edicai.ai.pending.action'].with_user(
            self.mgr).browse(reply['pending_id'])

    # -- 01..04 deny-by-default staging ---------------------------------

    def test_01_staging_denied_without_write_grant(self):
        with self.assertRaises(UserError):
            self._stage_create()

    def test_02_staging_denied_when_ops_lack_create(self):
        self.entity.write({
            'write_groups': 'edicai_ai.group_edicai_ai_user',
        })
        with self.assertRaises(UserError):
            self._stage_create()
        with self.assertRaises(UserError):
            self._stage_update(self.student_b, {'name': 'X'})

    def test_03_staging_denied_for_foreign_model(self):
        self._grant_writes()
        for model in ('res.partner', 'edicai.ai.chat.session', 'ir.model'):
            with self.assertRaises(UserError):
                self.tools.tool_entity_create({
                    'session_id': self.session.id,
                    'model': model,
                    'values': {'name': 'X'},
                })

    def test_04_staging_rejects_unwritable_values(self):
        self._grant_writes()
        must_reject = [
            # identity / server-owned / readonly-computed fields
            {'id': 7},
            {'company_id': 7},
            {'student_id_number': 7},
            # charged selection value
            {'gender': 'alien'},
            # unparseable date
            {'date_of_birth': 'not-a-date'},
            # unknown field
            {'not_a_field': 1},
            # create requires the required writable fields
            {'mobile': ''},
        ]
        for patch in must_reject:
            with self.assertRaises(UserError):
                self._stage_create(values_patch=patch)
        with self.assertRaises(UserError):
            self._stage_update(self.student_b, {'company_id': 7})
        # nothing was written anywhere
        name = self.env['edicai.student'].search_count(
            [('name', '=', 'G2 Created Student')])
        self.assertEqual(name, 0)

    # -- 05..08 proposal → confirm → executed ---------------------------

    def test_05_create_proposal_stages_preview_never_writes(self):
        self._grant_writes()
        before = self.env['edicai.student'].search_count([])
        reply = self._stage_create()
        self.assertTrue(reply['requires_confirmation'])
        self.assertEqual(reply['status'], STATUS_PREVIEW)
        self.assertFalse(reply['superseded'])
        row = self._pending(reply)
        self.assertEqual(row.action, ACTION_ENTITY_CREATE)
        self.assertTrue(row.ref)
        # no write happened
        self.assertEqual(
            self.env['edicai.student'].search_count([]), before)

    def test_06_confirm_executes_create_once_as_caller(self):
        self._grant_writes()
        reply = self._stage_create()
        row = self._pending(reply)
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')
        created = self.env['edicai.student'].browse(
            outcome['verified']['id'])
        self.assertTrue(created.exists())
        self.assertEqual(created.name, 'G2 Created Student')
        self.assertEqual(created.campus_id.id, self.campus.id)
        # single-effect: a second confirmation mutates nothing
        doubled = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(doubled['outcome'], 'not_confirmable')
        self.assertEqual(row.status, STATUS_EXECUTED)
        self.assertEqual(outcome['verified']['model_label'], 'Students')

    def test_07_update_proposal_renames_on_confirm(self):
        self._grant_writes()
        before = self.student_b.name
        reply = self._stage_update(self.student_b,
                                   {'name': 'Diya Renamed'})
        row = self._pending(reply)
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')
        self.assertEqual(
            self.student_b.browse(self.student_b.id).name,
            'Diya Renamed')
        self.assertEqual(row.result_res_id, self.student_b.id)
        # identity untouched: the ERP state machine stays authoritative
        self.assertNotEqual(before, 'Diya Renamed')

    def test_08_update_target_must_be_readable_and_real(self):
        self._grant_writes()
        ghost = self.student_b.id + 999999
        with self.assertRaises(UserError):
            self.tools.tool_entity_update({
                'session_id': self.session.id,
                'model': 'edicai.student',
                'record_id': ghost,
                'values': {'name': 'X'},
            })

    # -- 09..10 session ownership + supersede ---------------------------

    def test_09_other_users_session_rejected(self):
        self._grant_writes()
        # owned by ANOTHER AI user (staff) — the manager's tool env
        # must not touch it (owner-bound pending actions)
        with self.assertRaises(UserError):
            self.tools.tool_entity_create({
                'session_id': self.staff_session.id,
                'model': 'edicai.student',
                'values': {'name': 'X', 'gender': 'male',
                           'date_of_birth': '2008-01-01',
                           'email': 'a@b.c', 'mobile': '123',
                           'campus_id': self.campus.id,
                           'program_id': self.program.id},
            })

    def test_10_material_change_supersedes_the_old_preview(self):
        self._grant_writes()
        first = self._stage_create()
        second = self._stage_create(values_patch={
            'name': 'G2 Created Student 2'})
        self.assertTrue(second['superseded'])
        old = self._pending(first)
        self.assertEqual(old.status, STATUS_SUPERSEDED)
        # a superseded row can never execute
        outcome = old.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'not_confirmable')

    # -- 11..12 re-authorization at confirm time ------------------------

    def test_11_confirm_denied_when_grant_revoked(self):
        self._grant_writes()
        reply = self._stage_create()
        self._revoke_writes()
        row = self._pending(reply)
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(outcome['reason_code'], 'ENTITY_WRITE_GROUPS')
        # nothing was written and the row stays retryable at preview
        self.assertEqual(row.status, STATUS_PREVIEW)
        self.assertEqual(
            self.env['edicai.student'].search_count(
                [('name', '=', 'G2 Created Student')]), 0)
        # re-grant + confirm now executes
        self._grant_writes()
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')

    def test_12_confirm_denied_when_master_flag_off(self):
        self._grant_writes()
        reply = self._stage_create()
        self.env['ir.config_parameter'].set_param(ENTITY_FLAG, 'False')
        row = self._pending(reply)
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(
            outcome['reason_code'], 'ENTITY_WRITE_DISABLED')
        self.assertEqual(row.status, STATUS_PREVIEW)
        self.assertEqual(
            self.env['edicai.student'].search_count(
                [('name', '=', 'G2 Created Student')]), 0)

    # -- 13 entity.list_actions -----------------------------------------

    def test_13_list_actions_grant_filtered(self):
        row = self.env['edicai.ai.entity.action'].sudo().create({
            'model_ref': 'edicai.student',
            'action': 'move_section',
            'label': 'Move section',
            'allowed_groups': 'edicai_ai.group_edicai_ai_user',
            'needs_approval': True,
            'enabled': True,
        })
        hidden = self.env['edicai.ai.entity.action'].sudo().create({
            'model_ref': 'edicai.student',
            'action': 'secret_op',
            'label': 'Hidden',
            'allowed_groups': 'base.group_system',
            'needs_approval': True,
            'enabled': True,
        })
        reply = self.tools.tool_list_actions({'model': 'edicai.student'})
        names = [item['action'] for item in reply['actions']]
        self.assertIn('move_section', names)
        self.assertNotIn('secret_op', names)
        shown = [i for i in reply['actions']
                 if i['action'] == 'move_section'][0]
        self.assertTrue(shown['needs_approval'])
        row.unlink()
        hidden.unlink()

    # -- 16 the seed must never clobber manager grants ------------------

    def test_16_seed_records_are_noupdate_protected(self):
        """An upgrade must NOT reset a manager's grant/ops edits.

        The seeded policies are live configuration: without
        ``noupdate="1"`` every module upgrade rewrites ``ops`` back to
        the read-only default (silently closing a granted write).
        """
        import os
        path = os.path.join(
            os.path.dirname(__file__), '..', 'data',
            'ai_entity_policy_data.xml')
        with open(path, encoding='utf-8') as handle:
            xml = handle.read()
        records = [line for line in xml.split('\n')
                   if line.strip().startswith('<record id="entity_policy_')]
        self.assertEqual(len(records), 6)
        # the whole seed block is noupdate-protected (a <data
        # noupdate="1"> block — never a per-record attribute)
        self.assertIn('<data noupdate="1">', xml)
        self.assertEqual(xml.count('<data noupdate="1">'), 1)

    # -- 14 the CONVERSATIONAL confirm path executes the entity write --

    def test_14_chat_confirmation_executes_the_entity_write(self):
        """The generic lane opens with the G2 flag and the user's
        'confirm <ref>' turn performs the write end to end."""
        self._grant_writes()
        reply = self._stage_create()
        orchestrator = self.env['edicai.ai.action.orchestrator'].with_user(
            self.mgr)
        result = orchestrator.handle_turn(
            'confirm %s' % reply['pending_ref'], session=self.session)
        self.assertTrue(result, 'the entity lane must answer the turn')
        self.assertEqual(
            self.env['edicai.student'].search_count(
                [('name', '=', 'G2 Created Student')]), 1)
        # a SECOND confirmation is idempotent (no second record)
        result2 = orchestrator.handle_turn(
            'confirm %s' % reply['pending_ref'], session=self.session)
        self.assertTrue(result2)
        self.assertEqual(
            self.env['edicai.student'].search_count(
                [('name', '=', 'G2 Created Student')]), 1)

    def test_15_entity_lane_stays_closed_while_the_flag_is_off(self):
        """Without the G2 flag the lane does not even open (byte-identical
        Phase 1A refusal — no accidental writes)."""
        self._grant_writes()
        self.env['ir.config_parameter'].set_param(ENTITY_FLAG, 'False')
        reply = self._stage_create()
        orchestrator = self.env['edicai.ai.action.orchestrator'].with_user(
            self.mgr)
        result = orchestrator.handle_turn(
            'confirm %s' % reply['pending_ref'], session=self.session)
        # the turn is NOT handled by the action lane
        self.assertFalse(result)
        self.assertEqual(
            self.env['edicai.student'].search_count(
                [('name', '=', 'G2 Created Student')]), 0)

    # -- 17 a BUSINESS constraint at execution stays retryable -----------

    def test_17_model_constraint_at_execution_keeps_the_row_retryable(
            self):
        """Odoo's own constraints run at execution, not at staging.

        A student younger than 14 passes the generic type/required
        checks (it is a valid date) and only the STUDENT model refuses
        it AFTER the user confirmed. The layer must write nothing,
        report VALIDATION_FAILED and return the row to DRAFT so the
        user can restage with corrected values (never ``failed``).
        """
        self._grant_writes()
        reply = self._stage_create(
            values_patch={'date_of_birth': '2020-01-01'})
        row = self._pending(reply)
        self.assertEqual(row.status, STATUS_PREVIEW)
        outcome = row.with_user(self.mgr).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'error')
        self.assertEqual(outcome['error_code'], 'VALIDATION_FAILED')
        # nothing was written
        self.assertEqual(
            self.env['edicai.student'].search_count(
                [('name', '=', 'G2 Created Student')]), 0)
        # the row is RETRYABLE (draft), not failed
        fresh = self.Pending.browse(row.id)
        fresh.invalidate_recordset()
        self.assertEqual(fresh.status, STATUS_DRAFT)
        self.assertEqual(fresh.failure_reason, 'VALIDATION_FAILED')
        # the refusal is durably audited (reason-coded, no payload leak)
        event = self.env['edicai.ai.audit.event'].sudo().search([
            ('event_type', '=', 'ACTION_ERROR'),
            ('reason_code', '=', 'VALIDATION_FAILED'),
            ('tool_name', '=', 'entity.create'),
        ], order='id desc', limit=1)
        self.assertTrue(event)
        self.assertEqual(
            event.metadata_json.get('exception_type'), 'ValidationError')
