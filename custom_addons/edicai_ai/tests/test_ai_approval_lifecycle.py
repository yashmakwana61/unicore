"""Phase 4 — approval lifecycle tests over the REAL model API.

Covers: requester lifecycle (draft → preview → pending), canonical
submission, admin approval + canonical execution + verification,
self-approval block, unauthorized approver, duplicate approval,
rejection with bounded reason, withdrawal (§15), expiry (lazy + at
decision), hash-tamper fail-closed, material target change
fail-closed, concurrent-lock duplicate safety, missing-field flows
and the immutable write guard.
"""

from unittest import mock

from odoo.exceptions import AccessError

import odoo.tests
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_approval import (
    PARAM_APPROVAL_TIMEOUT,
    STATUS_CANCELLED,
    STATUS_EXECUTED,
    STATUS_EXPIRED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PREVIEW,
    STATUS_REJECTED,
)
from odoo.addons.edicai_ai.tests.phase4_common import (
    Phase4Fixtures,
)


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIApprovalLifecycleHarness(TransactionCase, Phase4Fixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_approval_core()

    # ------------------------------------------------------------------
    # Requester lifecycle
    # ------------------------------------------------------------------

    def test_01_full_requester_lifecycle_reaches_pending(self):
        row, outcome, session = self._approval_via_lifecycle()
        self.assertEqual(outcome['outcome'], 'submitted',
                         msg=repr(outcome))
        self.assertEqual(row.status, STATUS_PENDING)
        # The canonical underlying request exists and is submitted.
        Req = self.env['edicai.asset.request'].with_user(self.requester)
        target = Req.browse(row.request_res_id)
        self.assertEqual(target.state, 'submitted')
        self.assertEqual(target.requested_by.id, self.requester.id)
        # A SECOND hash froze the approval plan + the approval code.
        self.assertEqual(row.ref, row.plan_hash[:8])
        self.assertTrue(row.plan_hash)
        self.assertTrue(row.designated_approver_id)

    def test_02_preview_freezes_plan_and_is_immutable(self):
        row, reply, _s = self._start_approval()
        self.assertEqual(row.status, STATUS_PREVIEW)
        plan = row._read_plan()
        self.assertEqual(plan['effect'],
                         'create_and_submit_for_approval')
        self.assertEqual(plan['res_model'], 'edicai.asset.request')
        payload = row._read_vals()
        self.assertEqual(payload['asset_type'], 'projector')
        self.assertIn('Nothing has been changed yet.', reply['reply'])
        self.assertIn('confirm', reply['reply'])
        # External writes cannot unfreeze the material plan (§7).
        row.write({'reason': 'TAMPERED'})
        self.assertNotEqual(row._read_vals().get('reason'),
                            'TAMPERED')

    def test_03_missing_fields_are_asked_never_guessed(self):
        Approval = self.env['edicai.ai.pending.approval'] \
            .with_user(self.requester)
        reply = Approval.start_request(
            self.approval_session, {'asset_type': 'projector'})
        row = Approval.open_active(self.approval_session,
                                   self.requester)
        self.assertTrue(row)
        self.assertEqual(row.status, 'draft')
        self.assertIn('still need', reply['reply'])
        self.assertIn('reason', reply['reply'])
        # Supply the fields through the real merge path.
        reply2 = row.merge_payload({'reason': 'Lab sessions',
                                    'needed_by': 'tomorrow'})
        self.assertTrue(reply2[1])
        return row

    # ------------------------------------------------------------------
    # Approval + execution + verification
    # ------------------------------------------------------------------

    def test_04_approve_executes_canonical_and_verifies(self):
        row, _o, _s = self._approval_via_lifecycle()
        outcome = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')
        result = row._read_result()
        self.assertTrue(result['verified'])
        self.assertEqual(result['approved_by'], self.approver.name)
        Req = self.env['edicai.asset.request'].with_user(self.approver)
        target = Req.browse(row.request_res_id)
        self.assertEqual(target.state, 'approved')
        self.assertTrue(target.approved_date)
        self.assertEqual(STATUS_EXECUTED, row.status)
        self.assertEqual(row.approved_by_id.id, self.approver.id)
        # Evidence chain: APPROVED → EXECUTION_STARTED → EXECUTED.
        events = self.env['edicai.ai.audit.event'].search([
            ('tool_name', '=', 'asset.request.approval'),
        ]).mapped('event_type')
        for expected in ('APPROVAL_APPROVED',
                         'APPROVAL_EXECUTION_STARTED',
                         'APPROVAL_EXECUTED'):
            self.assertIn(expected, events)

    def test_05_self_approval_is_impossible(self):
        row, _o, _s = self._approval_via_lifecycle()
        outcome = row.with_user(self.requester).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(outcome['reason_code'], 'SELF_APPROVAL')
        target = self.env['edicai.asset.request'].with_user(
            self.requester).browse(row.request_res_id)
        self.assertEqual(target.state, 'submitted')
        events = self.env['edicai.ai.audit.event'].search([
            ('tool_name', '=', 'asset.request.approval'),
            ('event_type', '=', 'APPROVAL_AUTH_DENIED'),
        ])
        self.assertTrue(events)

    def test_06_unauthorized_approver_denied(self):
        row, _o, _s = self._approval_via_lifecycle()
        outcome = row.with_user(self.bystander).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(outcome['reason_code'], 'NOT_AN_APPROVER')
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        self.assertEqual(target.state, 'submitted')
        self.assertEqual(row.status, STATUS_PENDING)

    def test_07_duplicate_approval_never_executes_twice(self):
        row, _o, _s = self._approval_via_lifecycle()
        first = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(first['outcome'], 'executed')
        Req = self.env['edicai.asset.request'].with_user(self.approver)
        messages = Req.env['mail.message'].search_count([
            ('model', '=', 'edicai.asset.request'),
            ('res_id', '=', row.request_res_id),
            ('body', 'ilike', 'approved'),
        ])
        again = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(again['outcome'], 'not_pending')
        messages2 = Req.env['mail.message'].search_count([
            ('model', '=', 'edicai.asset.request'),
            ('res_id', '=', row.request_res_id),
            ('body', 'ilike', 'approved'),
        ])
        self.assertEqual(messages, messages2)

    def test_08_concurrent_lock_deduplicates(self):
        row, _o, _s = self._approval_via_lifecycle()
        with mock.patch.object(
                type(row), '_lock_nowait', return_value=False):
            outcome = row.with_user(
                self.approver).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'duplicate_concurrent')
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        self.assertEqual(target.state, 'submitted')

    # ------------------------------------------------------------------
    # Rejection
    # ------------------------------------------------------------------

    def test_09_rejection_is_canonical_and_terminal(self):
        row, _o, _s = self._approval_via_lifecycle()
        outcome = row.with_user(self.approver).reject_and_execute(
            'duplicate of an existing one')
        self.assertEqual(outcome['outcome'], 'rejected')
        self.assertEqual(row.status, STATUS_REJECTED)
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        self.assertEqual(target.state, 'rejected')
        # The bounded reason is stored; the row is terminal.
        self.assertEqual(row.rejection_reason,
                         'duplicate of an existing one')
        post = row.with_user(self.approver).reject_and_execute()
        self.assertEqual(post['outcome'], 'not_pending')

    def test_10_rejection_without_reason_and_by_bystander(self):
        row, _o, _s = self._approval_via_lifecycle()
        denied = row.with_user(self.bystander).reject_and_execute('x')
        self.assertEqual(denied['outcome'], 'denied')
        self.assertEqual(denied['reason_code'], 'NOT_AN_APPROVER')
        ok = row.with_user(self.approver).reject_and_execute(None)
        self.assertEqual(ok['outcome'], 'rejected')
        self.assertEqual(row.rejection_reason, '')

    # ------------------------------------------------------------------
    # Withdrawal (§15)
    # ------------------------------------------------------------------

    def test_11_withdraw_before_submit_is_free(self):
        row, _reply, _s = self._start_approval()
        outcome = row.with_user(self.requester).cancel()
        self.assertEqual(outcome['outcome'], 'cancelled')
        # Nothing was ever created in the business layer.
        Req = self.env['edicai.asset.request'].with_user(self.requester)
        created = Req.search_count([
            ('requested_by', '=', self.requester.id),
            ('reason', '=', 'Semester lab sessions'),
        ])
        self.assertEqual(created, 0)

    def test_12_withdraw_pending_never_invents_business_cancel(self):
        row, _o, _s = self._approval_via_lifecycle()
        outcome = row.with_user(self.requester).cancel()
        self.assertEqual(outcome['outcome'], 'cancelled')
        self.assertEqual(row.status, STATUS_CANCELLED)
        # The module has NO cancel action: the request stays submitted
        # and is reported honestly (no invented business semantics).
        target = self.env['edicai.asset.request'].with_user(
            self.requester).browse(row.request_res_id)
        self.assertEqual(target.state, 'submitted')
        self.assertEqual(outcome.get('target_state'), 'submitted')
        # A withdrawn approval can never execute afterward (terminal).
        blocked = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(blocked['outcome'], 'not_pending')

    def test_13_only_the_requester_withdraws(self):
        row, _o, _s = self._approval_via_lifecycle()
        outcome = row.with_user(self.approver).cancel()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(outcome['reason_code'], 'NOT_THE_REQUESTER')
        self.assertEqual(row.status, STATUS_PENDING)

    # ------------------------------------------------------------------
    # Expiry (lazy + at decision) and preview timeout
    # ------------------------------------------------------------------

    def test_14_expired_pending_fails_closed_at_decision(self):
        row, _o, _s = self._approval_via_lifecycle()
        self._rewind_created(row, 1500)
        outcome = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'expired')
        self.assertEqual(row.status, STATUS_EXPIRED)
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        self.assertEqual(target.state, 'submitted')

    def test_15_lazy_expiry_sweep(self):
        row, _o, _s = self._approval_via_lifecycle()
        fresh, _o2, _s2 = self._approval_via_lifecycle(
            session=self._chat_session(self.requester,
                                       title='fresh'), user=None)
        self.assertEqual(fresh.status, STATUS_PENDING)
        self._rewind_created(row, 1501)
        self.env['edicai.ai.pending.approval'] \
            .with_user(self.approver).expire_pending()
        self.assertEqual(row.status, STATUS_EXPIRED)
        self.assertEqual(fresh.status, STATUS_PENDING)

    def test_16_preview_timeout_blocks_confirm(self):
        row, _reply, _s = self._start_approval()
        minutes = self.env['edicai.ai.action.policy'] \
            .get_confirm_timeout_minutes() + 10
        self._rewind_created(row, minutes)
        outcome = row.with_user(self.requester).confirm_and_submit()
        self.assertEqual(outcome['outcome'], 'expired_preview')
        Req = self.env['edicai.asset.request'].with_user(self.requester)
        created = Req.search_count([
            ('requested_by', '=', self.requester.id)])
        self.assertEqual(created, 0)

    # ------------------------------------------------------------------
    # Plan integrity + material change (§7)
    # ------------------------------------------------------------------

    def test_17_hash_tamper_fails_closed(self):
        row, _o, _s = self._approval_via_lifecycle()
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE edicai_ai_pending_approval SET plan_hash = %s "
            "WHERE id = %s", ('deadbeef' * 8, row.id))
        self.env['edicai.ai.pending.approval'].invalidate_model()
        row = self.env['edicai.ai.pending.approval'].with_user(
            self.approver).browse(row.id)
        outcome = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'hash_mismatch')
        self.assertEqual(row.status, STATUS_FAILED)
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        self.assertEqual(target.state, 'submitted')

    def test_18_material_target_change_fails_closed(self):
        row, _o, _s = self._approval_via_lifecycle()
        # Someone processes the request in the standard interface.
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        target.with_user(self.approver).action_reject()
        outcome = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'target_processed')
        self.assertEqual(outcome['target_state'], 'rejected')
        self.assertEqual(row.status, STATUS_CANCELLED)

    def test_18a_material_field_change_invalidates_pending_approval(self):
        row, _o, _s = self._approval_via_lifecycle()
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        original_state = target.state
        target.write({'reason': 'Changed after submission'})
        outcome = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'invalidated')
        self.assertEqual(row.status, 'invalidated')
        self.assertEqual(target.state, original_state)
        audit = self.env['edicai.ai.audit.event'].search([
            ('event_type', '=', 'APPROVAL_INVALIDATED'),
            ('tool_name', '=', 'asset.request.approval'),
        ], limit=1)
        self.assertTrue(audit)

    def test_18b_nonmaterial_chatter_change_keeps_approval_valid(self):
        row, _o, _s = self._approval_via_lifecycle()
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        target.message_post(body='Non-material audit note')
        outcome = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'executed')
        self.assertEqual(row.status, STATUS_EXECUTED)

    def test_19_target_unavailable_fails_closed(self):
        row, _o, _s = self._approval_via_lifecycle()
        # Remove the request entirely (superuser cleanup is a fixture
        # action, never a conversational path).
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        target.unlink()
        outcome = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'error')
        self.assertEqual(outcome['error_code'], 'TARGET_UNAVAILABLE')
        self.assertEqual(row.status, STATUS_FAILED)

    # ------------------------------------------------------------------
    # Write-guard transitions
    # ------------------------------------------------------------------

    def test_20_terminal_rows_are_not_resurrected(self):
        row, _o, _s = self._approval_via_lifecycle()
        row.with_user(self.requester).cancel()
        self.assertEqual(row.status, STATUS_CANCELLED)
        row.with_user(self.requester).write({'status':
                                             STATUS_PENDING})
        self.assertEqual(row.status, STATUS_CANCELLED)

    def test_21_pending_status_moves_through_executed_only(self):
        row, _o, _s = self._approval_via_lifecycle()
        row.with_user(self.requester).write({'status': 'draft'})
        self.assertEqual(row.status, STATUS_PENDING)

    # ------------------------------------------------------------------
    # Parameterization
    # ------------------------------------------------------------------

    def test_22_approval_timeout_parameterized(self):
        policy = self.env['edicai.ai.action.policy']
        self.assertEqual(policy.get_approval_timeout_minutes(), 1440)
        self._set_ai_flag(PARAM_APPROVAL_TIMEOUT, '120')
        try:
            self.assertEqual(
                policy.get_approval_timeout_minutes(), 120)
        finally:
            self._set_ai_flag(PARAM_APPROVAL_TIMEOUT, '1440')

    # ------------------------------------------------------------------
    # Multi-company isolation (prompt §6/§22) + explicit self-approval
    # ------------------------------------------------------------------

    def test_23_cross_company_approver_denied_and_blind(self):
        row, _o, _s = self._approval_via_lifecycle()
        company2 = self.env['res.company'].create(
            {'name': 'Second Company APQ'})
        foreign_admin = self._create_staff_user(
            'FQA4', groups=('admin',))
        foreign_admin.write({
            'company_id': company2.id,
            'company_ids': [(6, 0, [company2.id])],
        })
        # Record rules: a foreign admin cannot even SEE the row, so
        # the lane resolves NOTHING for them (honest clarification,
        # never a decision).
        visible = self.env['edicai.ai.pending.approval'].with_user(
            foreign_admin).search([('id', '=', row.id)])
        self.assertFalse(visible)
        lane_row = self.env['edicai.ai.pending.approval'].with_user(
            foreign_admin).find_by_address('ref', row.ref)
        self.assertFalse(lane_row)
        # A foreign AI-MANAGER sits outside both author roles: the
        # global company rule isolates them TOO, so every lane entry
        # is blind — and a raw model touch fails closed (ORM proof).
        foreign_pm = self._create_staff_user(
            'FQM4', groups=('manager',))
        foreign_pm.write({
            'company_id': company2.id,
            'company_ids': [(6, 0, [company2.id])],
        })
        self.assertFalse(self.env['edicai.ai.pending.approval']
                         .with_user(foreign_pm).search_count(
                             [('id', '=', row.id)]))
        with self.assertRaises(AccessError):
            (self.env['edicai.ai.pending.approval']
             .with_user(foreign_pm).browse(row.id)
             .approve_and_execute())
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        self.assertEqual(target.state, 'submitted')

    def test_24_admin_requester_cannot_self_approve(self):
        approver_session = self._chat_session(
            self.approver, title='self-approval')
        row, _o, _s = self._approval_via_lifecycle(
            session=approver_session, user=self.approver)
        outcome = row.with_user(self.approver).approve_and_execute()
        self.assertEqual(outcome['outcome'], 'denied')
        self.assertEqual(outcome['reason_code'], 'SELF_APPROVAL')
        target = self.env['edicai.asset.request'].with_user(
            self.approver).browse(row.request_res_id)
        self.assertEqual(target.state, 'submitted')
