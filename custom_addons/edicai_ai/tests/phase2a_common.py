"""Shared Phase 2A test infrastructure.

Builds on the proven Phase 1A fixtures (academic core) and adds:

* an ACTIVE admission cycle on the fixture campus,
* registrar / manager / admin write-group users and a plain
  staff user (AI user group only),
* the action-flag helpers and the canonical full payload.

Everything is created under record rules intact — never with ``sudo``.
"""

from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures

FLAG_ACTION_WRITE = 'edicai_ai.action_write_enabled'
FLAG_ORCHESTRATOR = 'edicai_ai.orchestrator_enabled'
FLAG_CONVERSATION_LLM = 'edicai_ai.conversation_llm_enabled'
FLAG_LLM_COMPOSITION = 'edicai_ai.llm_composition_enabled'

ALL_AI_FLAGS = (
    FLAG_ACTION_WRITE, FLAG_ORCHESTRATOR, FLAG_CONVERSATION_LLM,
    FLAG_LLM_COMPOSITION,
)

_TIMEOUT_PARAM = 'edicai_ai.action_confirm_timeout_minutes'


class Phase2AFixtures(Phase1AFixtures):
    """Mixin for Phase 2A test classes."""

    @classmethod
    def _build_action_core(cls, suffix='2A'):
        """Academic core + active admission cycle + users."""
        cls._build_academic_core(suffix=suffix)
        cls.cycle = cls.env['edicai.admission.cycle'].create({
            'name': 'Test Cycle 2030-31%s' % suffix,
            'code': 'TCYC%s' % suffix,
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2030-07-01',
            'end_date': '2031-05-31',
            'state': 'active',
            'company_id': cls.company.id,
        })
        cls.registrar = cls._create_staff_user(
            login_suffix='%sreg' % suffix, groups=('registrar',))
        cls.manager = cls._create_staff_user(
            login_suffix='%smgr' % suffix, groups=('manager',))
        cls.bare_staff = cls._create_staff_user(
            login_suffix='%sstf' % suffix)
        return cls

    @classmethod
    def _set_ai_flag(cls, key, value):
        cls.env['ir.config_parameter'].sudo().set_param(key, value)

    @classmethod
    def _action_flags(cls, on=True):
        for key in ALL_AI_FLAGS:
            cls._set_ai_flag(key, ('True' if on else 'False')
                             if key == FLAG_ACTION_WRITE else
                             ('True' if key == FLAG_ORCHESTRATOR
                              else 'False'))

    @classmethod
    def _confirm_timeout(cls, minutes):
        cls._set_ai_flag(_TIMEOUT_PARAM, str(minutes))

    @classmethod
    def _chat_session(cls, user, title='Action fixture'):
        """A chat session owned by ``user`` (created as that user)."""
        return cls.env['edicai.ai.chat.session'].with_user(user).create({
            'title': title,
        })

    @classmethod
    def _applicant_payload(cls, email, program=None, campus=None,
                           cycle=None, **overrides):
        """Full valid payload hinting at THIS class's fixture records.

        Record hints use full unique names so resolution is
        deterministic in a shared test database.
        """
        payload = {
            'name': 'Ada Lovelace',
            'email': email,
            'mobile': '919900011122',
            'gender': 'male',
            'date_of_birth': '2004-03-15',
            'cycle': cycle or 'TCYC2A',
            'program': program or 'Test BSc Physics2A',
            'campus': campus or 'Test Central Campus2A',
        }
        payload.update(overrides)
        return payload
