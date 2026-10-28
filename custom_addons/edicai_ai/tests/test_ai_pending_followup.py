"""Phase 2B — pending-action lifecycle tests for the follow-up action.

Preview before mutation; action-bound confirmation; immutability;
idempotency (locked, exactly-once); re-authorization; verification;
duplicate handling; cancellation; expiry.
"""

from unittest import mock
from datetime import timedelta

import odoo.tests
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_action_resolve import (
    ACTION_SCHEDULE_FOLLOWUP,
)
from odoo.addons.edicai_ai.tests.phase2b_common import (
    FLAG_ACTION_FOLLOWUP,
    FLAG_ACTION_WRITE,
    Phase2BFixtures,
)


@odoo.tests.tagged('edicai', 'security', '-at_install', 'post_install')
class TestPendingFollowupLifecycle(TransactionCase, Phase2BFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_followup_core(suffix='PFU')
        cls._set_ai_flag(FLAG_ACTION_WRITE, 'True')
        cls._set_ai_flag(FLAG_ACTION_FOLLOWUP, 'True')
        cls._confirm_timeout(15)

    def _todo_id(self):
        return self.env.ref('mail.mail_activity_data_todo')

    def test_01_row_action_and_canonical_payload(self):
        row, _session = self._followup_row()
        self.assertEqual(row.action, ACTION_SCHEDULE_FOLLOWUP)
        payload = row._read_payload()
        self.assertEqual(payload.get('applicant'), 'Rahul Verma')
        self.assertTrue(payload.get('date'))
        # Draft-inquiry fields are NOT smuggled into the payload.
        self.assertNotIn('name', payload)

    def test_02_preview_binds_ref_and_audits(self):
        row, session = self._followup_row()
        self.assertEqual(row.status, 'preview')
        self.assertTrue(row.ref)
        self.assertTrue(row.action_hash)
        audits = self.env['edicai.ai.audit.event'].sudo().search([
            ('conversation_id', '=', session.id)])
        self.assertIn('ACTION_PREVIEW_CREATED', audits.mapped(
            'event_type'))

    def test_03_confirm_schedules_exactly_one_activity(self):
        row, session = self._followup_row()
        before = self._activity_count(self.applicant)
        registrar_env = self.env(user=self.registrar.id)
        outcome = row.with_env(registrar_env).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')
        self.assertEqual(row.status, 'executed')
        self.assertEqual(self._activity_count(self.applicant), before + 1)
        todo = self._todo_id()
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'edicai.admission.applicant'),
            ('res_id', '=', self.applicant.id),
            ('activity_type_id', '=', todo.id),
            ('user_id', '=', self.registrar.id),
        ])
        self.assertEqual(len(activity), 1)
        expected = self._resolve_anchor() + timedelta(days=1)
        self.assertEqual(activity.date_deadline, expected)
        self.assertIn('Purpose:', activity.note or '')
        self.assertEqual(row.result_res_id, activity.id)
        self.assertEqual(row.result_application_number,
                         self.applicant.application_number)
        audits = self.env['edicai.ai.audit.event'].sudo().search([
            ('conversation_id', '=', session.id)])
        event_types = set(audits.mapped('event_type'))
        self.assertIn('ACTION_CONFIRMED', event_types)
        self.assertIn('ACTION_EXECUTED', event_types)
        self.assertIn('ACTION_VERIFIED', event_types)

    def test_04_repeated_confirmation_never_schedules_twice(self):
        row, _session = self._followup_row()
        registrar_env = self.env(user=self.registrar.id)
        row.with_env(registrar_env).confirm_and_execute()
        row = self.env['edicai.ai.pending.action'].browse([row.id])
        outcome = row.with_env(registrar_env).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'not_confirmable')
        self.assertEqual(self._activity_count(self.applicant), 1)

    def test_05_concurrent_confirmation_is_single_effect(self):
        row, _session = self._followup_row()
        with mock.patch.object(
                type(row), '_lock_nowait',
                side_effect=lambda self_param: False, autospec=True):
            outcome = row.with_env(self.env(user=self.registrar.id)) \
                .confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'duplicate_concurrent')
        self.assertEqual(self._activity_count(self.applicant), 0)
        self.assertEqual(row.status, 'preview')

    def test_06_unauthorized_user_denied_at_execution(self):
        row, _session = self._followup_row(user=self.bare_staff)
        outcome = row.with_env(self.env(user=self.bare_staff.id)) \
            .confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(row.status, 'preview')
        self.assertEqual(self._activity_count(self.applicant), 0)
        audits = self.env['edicai.ai.audit.event'].sudo()
        self.assertIn('ACTION_AUTHORIZATION_DENIED', audits.search([
            ('conversation_id', '=', row.session_id.id),
        ]).mapped('event_type'))

    def test_07_material_change_supersedes_preview_row(self):
        row, _session = self._followup_row()
        old_ref = row.ref
        new_row, _changed, superseded = row.with_user(
            self.registrar).merge_fields({'purpose': 'Updated note'})
        self.assertTrue(superseded)
        self.assertEqual(new_row.status, 'draft')
        self.assertEqual(new_row.ref, False)
        self.assertEqual(
            new_row._read_payload().get('purpose'), 'Updated note')
        old_rows = self.env['edicai.ai.pending.action'].search([
            ('session_id', '=', new_row.session_id.id),
            ('id', '!=', new_row.id),
        ])
        self.assertTrue(all(r.status == 'superseded' for r in old_rows))
        self.assertTrue(all(r.ref == old_ref for r in old_rows))
        self.assertEqual(self._activity_count(self.applicant), 0)

    def test_08_execution_resolves_not_found_safely(self):
        row, _session = self._followup_row(applicant='Nobody Here',
                                           preview=False)
        row.mark_preview()
        registrar_env = self.env(user=self.registrar.id)
        outcome = row.with_env(registrar_env).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'not_found')
        self.assertEqual(self._activity_count(self.applicant), 0)

    def test_09_invalid_date_at_execution_fails_safely(self):
        # Force an unparseable phrase directly into a previewed row
        # (preview normally blocks this) to prove the last line of
        # defense.
        row, _session = self._followup_row(date='whenever someday')
        row._read_payload()
        row.write({'payload_json': '{"date": "whenever someday", '
                                   '"applicant": "Rahul Verma"}'})
        registrar_env = self.env(user=self.registrar.id)
        outcome = row.with_env(registrar_env).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'invalid_date')
        self.assertEqual(row.status, 'preview')
        self.assertEqual(self._activity_count(self.applicant), 0)

    def test_10_cancellation(self):
        row, session = self._followup_row()
        cancelled = row.with_user(self.registrar).cancel()
        self.assertTrue(cancelled)
        self.assertEqual(row.status, 'cancelled')
        self.assertEqual(self._activity_count(self.applicant), 0)
        audits = self.env['edicai.ai.audit.event'].sudo().search([
            ('conversation_id', '=', session.id)])
        self.assertIn('ACTION_CANCELLED', audits.mapped('event_type'))

    def test_11_ground_reply_snapshot_readonly(self):
        row, _session = self._followup_row()
        registrar_env = self.env(user=self.registrar.id)
        row.with_env(registrar_env).confirm_and_execute()
        fresh = self.env['edicai.ai.pending.action'].browse([row.id])
        snapshot = fresh.with_env(registrar_env)._read_result()
        self.assertEqual(snapshot['applicant'],
                         'Rahul Verma')
        self.assertTrue(snapshot['application_number'])
        self.assertEqual(snapshot['activity_id'], fresh.result_res_id)
