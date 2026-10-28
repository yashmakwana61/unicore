"""Shared Phase 4 test infrastructure.

Extends the Phase 3 fixtures with:

* the approval flag (``edicai_ai.approval_enabled``),
* the approval participants: a REQUESTER (faculty — the module's own
  asset-request creator per ``edicai_asset_request`` ACL) and an
  APPROVER (institution administrator — the repository's designated
  approval authority), plus a staff bystander for denial tests,
* helpers to run the REAL requester lifecycle (start → preview →
  confirm → submitted+pending) and to rewind ``create_date`` for
  deterministic expiry tests.

Everything is created through canonical user envs — never ``sudo`` —
except the lifecycle-internal audit/record freeze (Phase 4 model).
"""

from datetime import date, timedelta

from odoo.addons.edicai_ai.tests.phase3_common import (
    Phase3Fixtures,  # noqa: F401 — fixture chain base
)

FLAG_APPROVAL = 'edicai_ai.approval_enabled'
PARAM_APPROVAL_TIMEOUT = 'edicai_ai.approval_timeout_minutes'
FLAG_ACTION_WRITE = 'edicai_ai.action_write_enabled'
FLAG_ACTION_FOLLOWUP = 'edicai_ai.action_followup_enabled'
FLAG_WORKFLOW = 'edicai_ai.workflow_enabled'


class Phase4Fixtures(Phase3Fixtures):
    """Mixin for Phase 4 test classes."""

    @classmethod
    def _build_approval_core(cls, suffix='APQ'):
        """Phase 3 core + approval flag + approval participants."""
        cls._build_workflow_core(suffix=suffix)
        cls._set_ai_flag(FLAG_ACTION_WRITE, 'True')
        cls._set_ai_flag(FLAG_ACTION_FOLLOWUP, 'True')
        cls._set_ai_flag(FLAG_WORKFLOW, 'True')
        cls._set_ai_flag(FLAG_APPROVAL, 'True')
        cls.requester = cls._create_staff_user(
            'APR4', groups=('manager',))
        cls.approver = cls._create_staff_user(
            'APA4', groups=('admin',))
        cls.bystander = cls._create_staff_user(
            'APB4', groups=('staff',))
        cls.approval_session = cls._chat_session(
            cls.requester, title='Approval fixture A')
        cls.approver_session = cls._chat_session(
            cls.approver, title='Approval fixture B')

    # ------------------------------------------------------------------
    # Payload + canonical asset request helpers
    # ------------------------------------------------------------------

    @classmethod
    def _approval_payload(cls, **overrides):
        """A valid strict payload for the fixture campus."""
        payload = {
            'asset_type': 'projector',
            'reason': 'Semester lab sessions',
            'needed_by': 'tomorrow',
            'campus': 'Central',
        }
        payload.update(overrides)
        return payload

    @classmethod
    def _asset_request(cls, wanted_by=None, submit=True, **overrides):
        """A canonical asset request (via the module's own API)."""
        user = wanted_by or cls.requester
        vals = {
            'campus_id': cls.campus.id,
            'asset_type': 'projector',
            'asset_description': 'Ceiling projector',
            'reason': 'Fixture request',
            'needed_by_date': str(date.today() + timedelta(days=3)),
        }
        vals.update(overrides)
        Req = cls.env['edicai.asset.request'].with_user(user)
        record = Req.create(vals)
        if submit:
            record.action_submit()
        return record

    # ------------------------------------------------------------------
    # Real requester lifecycle (start → preview → confirm)
    # ------------------------------------------------------------------

    def _start_approval(self, session=None, user=None, payload=None):
        """Start a draft through the REAL model API.

        :returns: ``(row, reply, session)`` — row under the user env.
        """
        user = user or self.requester
        session = session or self.approval_session
        Approval = self.env['edicai.ai.pending.approval'].with_user(user)
        reply = Approval.start_request(
            session, dict(payload or self._approval_payload()))
        row = Approval.open_active(session, user)
        return row, reply, session

    def _approval_via_lifecycle(self, session=None, user=None,
                                payload=None):
        """The WHOLE requester path through the real lifecycle.

        :returns: ``(row, outcome, session)`` — pending approval row.
        """
        row, _reply, session = self._start_approval(
            session=session, user=user, payload=payload)
        self.assertTrue(row, 'approval draft row expected')
        outcome = row.with_user(user or self.requester) \
            .confirm_and_submit()
        row = self.env['edicai.ai.pending.approval'].with_user(
            user or self.requester).open_active(session, user) or row
        return row, outcome, session

    def _row_any(self, session=None, user=None):
        """Most recent approval row of (session, requester)."""
        Approval = self.env['edicai.ai.pending.approval'].with_user(
            user or self.requester)
        return Approval.find_for_user_session(
            session or self.approval_session, user or self.requester)

    def _rewind_created(self, row, minutes):
        """Deterministic pending-expiry rewind (flush before SQL)."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE edicai_ai_pending_approval "
            "SET create_date = (NOW() AT TIME ZONE 'utc') "
            "- INTERVAL '%s minutes' WHERE id = %%s" % int(minutes),
            [row.id])
        self.env['edicai.ai.pending.approval'].invalidate_model()

    def _reset_expiry(self, minutes=None):
        """Restore the deterministic default approval window."""
        self._set_ai_flag(PARAM_APPROVAL_TIMEOUT,
                          str(minutes if minutes is not None
                              else 1440))
