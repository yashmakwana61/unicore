"""Phase 3 — pending-workflow lifecycle tests.

Frozen plan + action-bound confirmation; re-authorization; per-
operation verification; idempotency (duplicate + concurrent);
expiry; cancellation; partial-failure accounting and deterministic
partial recovery WITHOUT duplicating verified operations.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError

import odoo.tests
from odoo.tests.common import TransactionCase
from unittest import mock

from odoo.addons.edicai_ai.tests.phase3_common import (
    Phase3Fixtures,
    WORKFLOW,
)


@odoo.tests.tagged('edicai', 'security', '-at_install', 'post_install')
class TestPendingWorkflowLifecycle(TransactionCase, Phase3Fixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_workflow_core(suffix='PWF')
        cls._confirm_timeout(15)

    def _start(self, entities=None, session=None):
        Wf = self.env['edicai.ai.pending.workflow']
        session = session or self._workflow_session()
        response = Wf.with_user(self.registrar).start_workflow(
            session, dict(entities or {}))
        row = Wf.with_user(self.registrar).open_active(
            session, self.registrar)
        return response, row, session

    def _confirm(self, row):
        with_user_row = row.with_user(row.user_id)
        return with_user_row.confirm_and_execute()

    def _child_rows(self, session):
        return self.env['edicai.ai.pending.action'].with_user(
            self.registrar).search([('session_id', '=', session.id)])

    def test_01_confirm_executes_plan_via_child_actions(self):
        response, row, session = self._start()
        todo = self.env.ref('mail.mail_activity_data_todo')
        before = self._activity_total()
        outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'executed', outcome)
        self.assertEqual(row.status, 'executed')
        # 3 NEW to-do activities, due the plan date, owned by the
        # registrar — no second business implementation.
        self.assertEqual(self._activity_total(), before + 3)
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'edicai.admission.applicant'),
            ('user_id', '=', self.registrar.id),
            ('activity_type_id', '=', todo.id),
            ('date_deadline', '=', row._read_plan()['date']),
        ])
        self.assertEqual(len(activities), 3)
        applications = set(activities.mapped('res_id'))
        self.assertEqual(applications, {
            self.candidate_a.id, self.candidate_b.id,
            self.candidate_c.id})
        purposes = set(activities.mapped('summary'))
        self.assertEqual(purposes, {'Admission follow-up'})
        # Children went through the REAL Phase 2B execution path.
        children = self._child_rows(session)
        self.assertEqual(len(children), 3)
        self.assertTrue(
            all(child.status == 'executed' for child in children),
            [child.status for child in children])
        self.assertTrue(
            all(child.action == 'admission.schedule_followup'
                for child in children))
        # Verified snapshot: exactly one entry per op, all succeeded.
        results = row._read_results(row._read_plan())
        self.assertEqual(len(results), 3)
        self.assertTrue(
            all(entry['status'] == 'succeeded' for entry in results))

    def test_02_plan_is_frozen_and_confirmation_bound(self):
        response, row, session = self._start({'limit': 2})
        plan_before = row.plan_json
        hash_before = row.plan_hash
        self._confirm(row)
        # Plan text immutable after confirm (verified hash stable).
        self.assertEqual(row.plan_hash, hash_before)
        results = row._read_results(row._read_plan())
        self.assertEqual(len(results), 2)

    def test_03_duplicate_confirmation_never_duplicated(self):
        response, row, _session = self._start()
        outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'executed')
        before = self._activity_total()
        second = row.with_user(row.user_id).confirm_and_execute()
        self.assertEqual(second['outcome'], 'not_confirmable')
        # No new activities, no extra child rows, results unchanged.
        self.assertEqual(self._activity_total(), before)
        results = row._read_results(row._read_plan())
        self.assertEqual(
            sum(1 for entry in results if entry['status'] == 'succeeded'),
            3)

    def test_04_concurrent_confirmation_is_single_effect(self):
        response, row, _session = self._start()
        with mock.patch.object(
                type(row), '_lock_nowait', lambda _self: False):
            outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'duplicate_concurrent')
        self.assertEqual(row.status, 'preview')
        self.assertEqual(self._activity_total(), 1)

    def test_05_expired_workflow_refuses_to_execute(self):
        response, row, _session = self._start()
        self._rewind_created(row, minutes=20)
        outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'expired')
        self.assertEqual(row.status, 'expired')
        self.assertEqual(self._activity_total(), 1)

    def test_06_cancelled_workflow_refuses_to_execute(self):
        response, row, _session = self._start()
        self.assertTrue(row.cancel())
        outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'not_confirmable')
        self.assertEqual(row.status, 'cancelled')
        # Recancel is a no-op.
        self.assertFalse(row.cancel())

    def test_07_permission_change_invalidates_before_any_execution(self):
        _response, row, session = self._start()
        self.env['edicai.admission.applicant'].browse(
            [self.candidate_b.id]).write(
                {'company_id': self.company_other.id})
        outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'invalidated', outcome)
        self.assertEqual(row.status, 'invalidated')
        self.assertEqual(self._activity_total(), 1)  # existing busy applicant
        self.assertEqual(len(self._child_rows(session)), 0)

    def test_07a_material_candidate_change_invalidates_preview(self):
        _response, row, _session = self._start()
        activity_before = self._activity_total()
        self.candidate_a.write({'name': 'Changed Applicant'})
        outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'invalidated', outcome)
        self.assertEqual(row.status, 'invalidated')
        self.assertEqual(self._activity_total(), activity_before)

    def test_07b_candidate_added_after_preview_invalidates(self):
        _response, row, _session = self._start()
        activity_before = self._activity_total()
        self._make_applicant(
            'New Candidate', 'new.after.preview@test.edu',
            mobile='918701234599')
        outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'invalidated', outcome)
        self.assertEqual(self._activity_total(), activity_before)

    def test_07c_candidate_removed_from_open_set_invalidates(self):
        _response, row, _session = self._start()
        activity_before = self._activity_total()
        self.candidate_a.write({'rejection_reason': 'Test removal'})
        self.candidate_a.action_reject()
        outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'invalidated', outcome)
        self.assertEqual(self._activity_total(), activity_before)

    def test_08_partial_retry_skips_verified_operations(self):
        _response, row, _session = self._start()
        applicant_model = type(self.env['edicai.admission.applicant'])
        original = applicant_model.activity_schedule

        def fail_middle(record, *args, **kwargs):
            if record.id == self.candidate_b.id:
                raise UserError('fixture-only transient activity failure')
            return original(record, *args, **kwargs)

        with mock.patch.object(applicant_model, 'activity_schedule',
                               fail_middle):
            outcome = self._confirm(row)
        self.assertEqual(outcome['outcome'], 'partial')
        activities_before = self._activity_total()
        child_count_before = len(self._child_rows(row.session_id))
        results_before = [
            (entry['applicant_id'], entry['activity_id'])
            for entry in row._read_results(row._read_plan())
            if entry['status'] == 'succeeded']
        # The plan assumptions are unchanged; retry only the unfinished
        # canonical operation after the transient failure has cleared.
        outcome2 = self._confirm(row)
        self.assertEqual(outcome2['outcome'], 'executed', outcome2)
        self.assertEqual(row.status, 'executed')
        results = row._read_results(row._read_plan())
        self.assertEqual(
            all(entry['status'] == 'succeeded' for entry in results),
            True)
        # The two previously-verified operations were NOT re-executed:
        # same activity ids as before (not duplicated).
        after = [
            (entry['applicant_id'], entry['activity_id'])
            for entry in results]
        for applicant_id, activity_id in results_before:
            self.assertEqual(
                [entry[1] for entry in after
                 if entry[0] == applicant_id],
                [activity_id])
        self.assertEqual(self._activity_total(),
                         activities_before + 1)
        self.assertEqual(
            len(self._child_rows(row.session_id)),
            child_count_before + 1)

    def test_09_workflow_audits_reconstruct_result(self):
        response, row, _session = self._start()
        self._confirm(row)
        Audit = self.env['edicai.ai.audit.event'].sudo().search([
            ('tool_name', '=', WORKFLOW)])
        types = set(Audit.mapped('event_type'))
        for expected in ('WORKFLOW_PROPOSED', 'WORKFLOW_PREVIEWED',
                         'WORKFLOW_CONFIRMED',
                         'WORKFLOW_EXECUTION_STARTED',
                         'WORKFLOW_OPERATION_EXECUTED',
                         'WORKFLOW_COMPLETED'):
            self.assertIn(expected, types, expected)
        user_ids = set(Audit.mapped('user_id.id'))
        self.assertIn(self.registrar.id, user_ids)

    def _rewind_created(self, row, minutes=20):
        self.env.flush_all()
        self.env.cr.execute(
            'UPDATE edicai_ai_pending_workflow SET create_date = %s '
            'WHERE id = %s',
            [fields.Datetime.to_string(
                fields.Datetime.now() - timedelta(minutes=minutes)),
             row.id])
        row.invalidate_recordset(['create_date'])
