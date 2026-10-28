"""Shared Phase 3 test infrastructure.

Extends the Phase 2B fixtures with:

* the workflow flag (``edicai_ai.workflow_enabled``),
* a deterministic candidate set: three open inquiry applicants
  without any activity (the plan targets), one inquiry that already
  carries an open activity (excluded), one terminal-state applicant
  (excluded) and one foreign-company applicant (excluded),
* helpers to start a workflow plan and to read its state.

Everything is created through the canonical registrar env — never
``sudo`` — except the auxiliary second company (a fixture factory
action, not conversational state).
"""

from datetime import date, timedelta

from odoo.addons.edicai_ai.tests.phase2a_common import (
    Phase2AFixtures,  # noqa: F401 — fixture chain base
)
from odoo.addons.edicai_ai.tests.phase2b_common import (
    ALL_AI_FLAGS_2B,
    FLAG_ACTION_WRITE,
    FLAG_ACTION_FOLLOWUP,
    Phase2BFixtures,
)

FLAG_WORKFLOW = 'edicai_ai.workflow_enabled'

WORKFLOW = 'admission.prepare_followups'

ALL_AI_FLAGS_3 = ALL_AI_FLAGS_2B + (FLAG_WORKFLOW,)


class Phase3Fixtures(Phase2BFixtures):
    """Mixin for Phase 3 test classes."""

    @classmethod
    def _build_workflow_core(cls, suffix='WF3'):
        """Phase 2B core + workflow flag + deterministic candidates."""
        cls._build_action_core(suffix=suffix)
        cls._set_ai_flag(FLAG_ACTION_WRITE, 'True')
        cls._set_ai_flag(FLAG_ACTION_FOLLOWUP, 'True')
        cls._set_ai_flag(FLAG_WORKFLOW, 'True')
        low = suffix.lower()
        # Creation order defines the deterministic discovery order.
        cls.candidate_a = cls._make_applicant(
            'Priya Shah', 'priya.%s@test.edu' % low,
            mobile='918701234501')
        cls.candidate_b = cls._make_applicant(
            'Aarav Patel', 'aarav.%s@test.edu' % low,
            mobile='918701234502')
        cls.candidate_c = cls._make_applicant(
            'Ishaan Khan', 'ishaan.%s@test.edu' % low,
            mobile='918701234503')
        # Already has an OPEN activity → excluded by discovery.
        cls.busy_applicant = cls._make_applicant(
            'Devika Rao', 'devika.%s@test.edu' % low,
            mobile='918701234504')
        cls.busy_applicant.with_user(cls.registrar).activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            date_deadline=date.today() + timedelta(days=30),
            summary='Existing manual plan',
            note='',
            user_id=cls.registrar.id)
        # Terminal admission state → excluded by discovery.
        cls.terminal_applicant = cls._make_applicant(
            'Zaid Mirza', 'zaid.%s@test.edu' % low,
            mobile='918701234505', state='rejected')
        # Foreign company → excluded by discovery (company isolation).
        # Its default admission pipeline must exist BEFORE the
        # registrar-created applicant (the registrar cannot create
        # stages in a foreign company).
        cls.company_other = cls.env['res.company'].create({
            'name': 'Other Institute %s' % suffix,
        })
        cls.env['edicai.admission.stage']._ensure_default_stages(
            cls.company_other)
        # The registrar CANNOT create records in a foreign company
        # (record rules) — this foreign applicant is DB fixture state,
        # created under the admin env on purpose.
        cls.foreign_applicant = cls.env['edicai.admission.applicant'].create({
            'name': 'Ved Kapoor',
            'email': 'ved.%s@test.edu' % low,
            'mobile': '918701234506',
            'gender': 'male',
            'date_of_birth': '2004-03-15',
            'cycle_id': cls.cycle.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'company_id': cls.company_other.id,
            'state': 'inquiry',
        })
        return cls

    @classmethod
    def _workflow_flag(cls, on=True):
        cls._set_ai_flag(FLAG_WORKFLOW, 'True' if on else 'False')

    @classmethod
    def _open_candidate_count(cls, company=None):
        """Direct ground truth of the repository rule in the DB."""
        domain = [
            ('company_id', '=', (company or cls.company).id),
            ('state', 'in', [
                'inquiry', 'applied', 'documents_pending',
                'under_review', 'shortlisted', 'entrance_scheduled',
                'merit_listed', 'offer_sent', 'fee_pending',
                'waitlisted',
            ]),
        ]
        return cls.env['edicai.admission.applicant'].search_count(domain)

    def _activity_total(self, applicant=None):
        todo = self.env.ref('mail.mail_activity_data_todo')
        domain = [
            ('res_model', '=', 'edicai.admission.applicant'),
            ('activity_type_id', '=', todo.id),
        ]
        if applicant is not None:
            domain += [('res_id', '=', applicant.id)]
        return self.env['mail.activity'].search_count(domain)

    def _workflow_session(self, user=None, title='Workflow fixture'):
        return self._chat_session(user or self.registrar, title=title)

    def _start_workflow_row(self, session=None, entities=None,
                            user=None):
        """Start a plan through the REAL model API; returns (row, msg)."""
        Wf = self.env['edicai.ai.pending.workflow']
        session = session or self._workflow_session(user=user)
        response = Wf.with_user(user or self.registrar).start_workflow(
            session, dict(entities or {}))
        WfRow = Wf.with_user(user or self.registrar)
        row = WfRow.open_active(session, user or self.registrar)
        return row, response, session

    def _wf_confirm(self, session, user=None):
        """Confirm/execute through the actual model lifecycle."""
        Wf = self.env['edicai.ai.pending.workflow'].with_user(
            user or self.registrar)
        row = Wf.open_active(session, user or self.registrar)
        return row, row.confirm_and_execute()
