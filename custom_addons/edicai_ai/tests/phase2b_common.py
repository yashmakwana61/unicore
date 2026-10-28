"""Shared Phase 2B test infrastructure.

Extends the Phase 2A fixtures with an EXISTING admission applicant
(the follow-up target) and helpers for the schedule_followup action.
Applicants are created through the canonical registrar env — never
sudo.
"""

from datetime import timedelta

from odoo import fields

from odoo.addons.edicai_ai.tests.phase2a_common import (
    ALL_AI_FLAGS,
    FLAG_ACTION_WRITE,
    Phase2AFixtures,
)

FLAG_ACTION_FOLLOWUP = 'edicai_ai.action_followup_enabled'

ACTION_FOLLOWUP = 'admission.schedule_followup'

ALL_AI_FLAGS_2B = ALL_AI_FLAGS + (FLAG_ACTION_FOLLOWUP,)


class Phase2BFixtures(Phase2AFixtures):
    """Mixin for Phase 2B test classes."""

    @classmethod
    def _build_followup_core(cls, suffix='FUB', ambiguous=False):
        """Phase 2A core + followup flag + two existing applicants."""
        cls._build_action_core(suffix=suffix)
        cls._set_ai_flag(FLAG_ACTION_FOLLOWUP, 'True')
        low = suffix.lower()
        cls.applicant = cls._make_applicant(
            'Rahul Verma', 'rahul.%s@test.edu' % low,
            mobile='9198' + '1' * 10)
        if ambiguous:
            cls.applicant_alt = cls._make_applicant(
                'Rahul', 'rahul.alt.%s@test.edu' % low,
                mobile='9198' + '2' * 10)
        return cls

    @classmethod
    def _make_applicant(cls, name, email, mobile=None, state='inquiry',
                        **overrides):
        vals = dict(
            name=name,
            email=email,
            mobile=mobile or '9198000000',
            gender='male',
            date_of_birth='2004-03-15',
            cycle_id=cls.cycle.id,
            program_id=cls.program.id,
            campus_id=cls.campus.id,
            company_id=cls.company.id,
            state=state,
        )
        vals.update(overrides)
        return cls.env['edicai.admission.applicant'].with_user(
            cls.registrar).create(vals)

    @classmethod
    def _followup_payload(cls, applicant=None, date='tomorrow at '
                          '11 AM', purpose='Call about documents',
                          **overrides):
        if applicant is None:
            hint = 'Rahul Verma'
        elif hasattr(applicant, 'name'):
            hint = applicant.name
        else:
            hint = str(applicant)
        payload = {
            'applicant': hint,
            'date': date,
            'purpose': purpose,
        }
        payload.update(overrides)
        return payload

    @classmethod
    def _followup_flag(cls, on=True):
        cls._set_ai_flag(FLAG_ACTION_FOLLOWUP, 'True' if on else 'False')

    @classmethod
    def _resolve_anchor(cls, user=None):
        """The date anchor the resolver uses for THAT user's tz."""
        env = cls.env['edicai.ai.action.resolve'].with_user(
            user or cls.registrar)
        return fields.Date.context_today(env)

    def _followup_row(self, user=None, session=None, applicant=None,
                      preview=True, **overrides):
        user = user or self.registrar
        session = session or self._chat_session(
            user, title='followup fixture')
        Pending = self.env['edicai.ai.pending.action'].with_user(user)
        row = Pending.create_pending(
            session,
            self._followup_payload(applicant=applicant, **overrides),
            action=ACTION_FOLLOWUP)
        if preview:
            row.mark_preview()
        return row, session

    @classmethod
    def _activity_count(cls, applicant):
        todo = cls.env.ref('mail.mail_activity_data_todo')
        return cls.env['mail.activity'].search_count([
            ('res_model', '=', 'edicai.admission.applicant'),
            ('res_id', '=', applicant.id),
            ('activity_type_id', '=', todo.id),
        ])
