"""Phase 2A — pending-action lifecycle tests.

Preview before mutation; action-bound confirmation; immutability;
idempotency (locked, exactly-once); re-authorization; verification;
duplicate handling; cancellation; expiry; audits.
"""

from unittest import mock

import odoo.tests
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.tests.phase2a_common import (
    FLAG_ACTION_WRITE,
    Phase2AFixtures,
)


@odoo.tests.tagged('edicai', 'security', '-at_install', 'post_install')
class TestPendingActionLifecycle(TransactionCase, Phase2AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_action_core(suffix='PND')
        cls._set_ai_flag(FLAG_ACTION_WRITE, 'True')
        cls._confirm_timeout(15)

    def _new_preview_row(self, email='pnd_flow@test.edu', user=None,
                         **overrides):
        user = user or self.registrar
        session = self._chat_session(user)
        Pending = self.env['edicai.ai.pending.action'].with_user(user)
        payload = self._applicant_payload(
            email,
            program='Test BSc PhysicsPND',
            campus='Test Central CampusPND',
            cycle='TCYCPND',
            **overrides)
        row = Pending.create_pending(session, payload)
        row.mark_preview()
        return row, session

    def test_01_draft_supersede_and_merges(self):
        session = self._chat_session(self.registrar)
        Pending = self.env['edicai.ai.pending.action'].with_user(
            self.registrar)
        row = Pending.create_pending(session, {'name': 'Ada Lovelace'})
        self.assertEqual(row.status, 'draft')
        row, changed, superseded = row.merge_fields(
            {'email': 'pnd1@test.edu'})
        self.assertFalse(superseded)
        self.assertIn('email', changed)
        self.assertEqual(row._read_payload().get('email'),
                         'pnd1@test.edu')
        # A second active draft is impossible: starting one supersedes.
        other = Pending.create_pending(session, {'name': 'Bob'})
        self.assertEqual(other.status, 'draft')
        self.assertEqual(row.status, 'superseded')
        self.assertEqual(len(Pending.open_active(session)), 1)

    def test_02_preview_and_immutability_of_material_change(self):
        row, _session = self._new_preview_row(email='pnd2@test.edu')
        self.assertEqual(row.status, 'preview')
        self.assertTrue(row.ref)
        old_ref = row.ref
        row, changed, superseded = row.with_user(
            self.registrar).merge_fields({'program': 'Test BA HistoryPND'})
        self.assertTrue(superseded)
        self.assertEqual(row.status, 'draft')
        self.assertEqual(row.ref, False)
        old_row = self.env['edicai.ai.pending.action'].search([
            ('session_id', '=', row.session_id.id),
            ('id', '!=', row.id),
        ])
        self.assertTrue(old_row)
        self.assertTrue(all(r.ref == old_ref for r in old_row))
        self.assertEqual(len(old_row.mapped('status')), 1)
        self.assertEqual(old_row.mapped('status')[0], 'superseded')

    def test_03_execute_creates_verified_applicant(self):
        before = self.env['edicai.admission.applicant'].search_count([])
        row, _session = self._new_preview_row(email='pnd3@test.edu')
        registrar_env = self.env(user=self.registrar.id)
        outcome = row.with_env(registrar_env).confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')
        self.assertEqual(row.status, 'executed')
        created = self.env['edicai.admission.applicant'].search(
            [('email', '=', 'pnd3@test.edu')])
        self.assertEqual(len(created), 1)
        after = self.env['edicai.admission.applicant'].search_count([])
        self.assertEqual(after, before + 1)
        rec = created[0]
        self.assertEqual(rec.state, 'inquiry')
        self.assertEqual(rec.program_id.id, self.program.id)
        self.assertEqual(rec.campus_id.id, self.campus.id)
        self.assertEqual(rec.cycle_id.id, self.cycle.id)
        self.assertEqual(rec.company_id.id, self.company.id)
        self.assertEqual(rec.name, 'Ada Lovelace')
        self.assertTrue(rec.application_number)
        self.assertEqual(row.result_application_number,
                         rec.application_number)
        self.assertEqual(row.result_res_id, rec.id)
        # Audit chain present (preview → confirmed → executed → verified)
        Audit = self.env['edicai.ai.audit.event'].sudo().search([
            ('conversation_id', '=', row.session_id.id)])
        event_types = set(Audit.mapped('event_type'))
        self.assertIn('ACTION_PREVIEW_CREATED', event_types)
        self.assertIn('ACTION_CONFIRMED', event_types)
        self.assertIn('ACTION_EXECUTED', event_types)
        self.assertIn('ACTION_VERIFIED', event_types)

    def test_04_duplicate_application_never_created_twice(self):
        self.env['edicai.admission.applicant'].with_user(
            self.registrar).create({
                'name': 'Existing Applicant',
                'email': 'pnd4@test.edu',
                'mobile': '919111223344',
                'gender': 'other',
                'date_of_birth': '2003-11-02',
                'cycle_id': self.cycle.id,
                'program_id': self.program.id,
                'campus_id': self.campus.id,
                'state': 'inquiry',
                'company_id': self.company.id,
            })
        before = self.env['edicai.admission.applicant'].search_count([])
        row, _session = self._new_preview_row(email='pnd4@test.edu')
        outcome = row.with_env(self.env(user=self.registrar.id)) \
            .confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'duplicate_existing')
        after = self.env['edicai.admission.applicant'].search_count([])
        self.assertEqual(after, before)  # exactly zero new records
        self.assertEqual(row.status, 'failed')
        Audit = self.env['edicai.ai.audit.event'].sudo().search([
            ('conversation_id', '=', row.session_id.id)])
        self.assertIn('ACTION_DUPLICATE', Audit.mapped('event_type'))

    def test_05_expired_confirmation_cannot_execute(self):
        row, _session = self._new_preview_row(email='pnd5@test.edu')
        row_id = row.id
        self.env.cr.execute(
            'UPDATE edicai_ai_pending_action '
            "SET create_date = (now() - interval '2 hours') "
            'WHERE id = %s', [row_id])
        row.invalidate_recordset()
        outcome = row.with_env(self.env(user=self.registrar.id)) \
            .confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'expired')
        refreshed = self.env['edicai.ai.pending.action'].browse(row_id)
        self.assertEqual(refreshed.status, 'expired')
        self.assertEqual(
            self.env['edicai.admission.applicant'].search_count(
                [('email', '=', 'pnd5@test.edu')]), 0)

    def test_06_concurrent_confirmation_is_single_effect(self):
        row, _session = self._new_preview_row(email='pnd6@test.edu')
        with mock.patch.object(
                type(row), '_lock_nowait',
                side_effect=lambda self_param: False, autospec=True):
            outcome = row.with_env(self.env(user=self.registrar.id)) \
                .confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'duplicate_concurrent')
        self.assertEqual(
            self.env['edicai.admission.applicant'].search_count(
                [('email', '=', 'pnd6@test.edu')]), 0)
        self.assertEqual(row.status, 'preview')
        # The holder commits eventually: replay after execution is a
        # no-op duplicate, never a second record.
        row.mark_preview()  # already preview — no-op state sanity
        row.write({
            'status': 'executed',
            'executed_on': row.executed_on or '2020-01-01 00:00:00',
        })
        outcome = row.with_env(self.env(user=self.registrar.id)) \
            .confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'not_confirmable')

    def test_07_unauthorized_user_denied_at_execution(self):
        row, _session = self._new_preview_row(
            email='pnd7@test.edu', user=self.bare_staff)
        outcome = row.with_env(self.env(user=self.bare_staff.id)) \
            .confirm_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(row.status, 'preview')
        self.assertEqual(
            self.env['edicai.admission.applicant'].search_count(
                [('email', '=', 'pnd7@test.edu')]), 0)
        Audit = self.env['edicai.ai.audit.event'].sudo().search([
            ('conversation_id', '=', row.session_id.id)])
        self.assertIn('ACTION_AUTHORIZATION_DENIED',
                      Audit.mapped('event_type'))

    def test_08_cancellation(self):
        row, _session = self._new_preview_row(email='pnd8@test.edu')
        cancelled = row.with_user(self.registrar).cancel()
        self.assertTrue(cancelled)
        self.assertEqual(row.status, 'cancelled')
        self.assertEqual(
            self.env['edicai.admission.applicant'].search_count(
                [('email', '=', 'pnd8@test.edu')]), 0)
        Audit = self.env['edicai.ai.audit.event'].sudo().search([
            ('conversation_id', '=', row.session_id.id)])
        self.assertIn('ACTION_CANCELLED', Audit.mapped('event_type'))
        # A terminal row can never be modified silently: the payload
        # write is blocked by the lifecycle guard.
        revived_row, _changed, _super = row.with_user(
            self.registrar).merge_fields({'name': 'Zed'})
        self.assertEqual(revived_row._read_payload().get('name'),
                         'Ada Lovelace')
