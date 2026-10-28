r"""Phase G3 — the CODE-side registry of AI-executable record actions.

A record action is a *state-machine method the ERP already owns* (e.g.
"verify this document"). The AI layer never invents behaviour: it only
calls a method that is declared HERE, in code.

TWO independent gates must both pass before one record action runs:

* the DATA gate — an enabled ``edicai.ai.entity.action`` row for the
  (model, method) pair whose ``allowed_groups`` the caller holds, plus
  the entity policy granting ``execute`` (``execute_groups``);
* the CODE gate — this registry. A database row naming a method that is
  NOT declared here is refused no matter what the database says.

The split is deliberate. Data alone can never turn an arbitrary ORM
method into an AI capability: even somebody with write access to the
policy tables cannot add ``write``/``unlink``/``sudo``/``search``,
because those names are simply absent from this dict (and the payload
never carries a method name — the method is a fixed literal in the
spec, never a string from the database). Code alone grants nobody
access: every caller still needs the data grants.

Action specs are intentionally tiny and declarative:

``method``        the fixed Python method called on ONE record
``label``         fallback label (the data row's label wins)
``state_field``   column the action must leave in the expected state
``state_value``   the expected post-state (verification re-read)
``fields``        columns copied into the verified result (never PII)
``params``        closed parameter grammar: name → target field + cap

Adding an action is a code change reviewed like any other code change —
which is the whole point.
"""

import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Sanitized messages (never leak model internals to the chat reply).
ERROR_ACTION_PARAMS = 'The action parameters are missing or invalid.'
ERROR_ACTION_UNAVAILABLE = (
    'This record action cannot be executed on this record.')


def _note_param(target, max_len=500):
    return {'target': target, 'max_len': max_len}


#: THE closed registry. Keys are (model, method) as declared in the
#: ``edicai.ai.entity.action`` rows. Nothing else is callable.
ENTITY_ACTIONS = {
    ('edicai.student', 'action_activate'): {
        'method': 'action_activate',
        'label': 'Activate student',
        'state_field': 'student_state',
        'state_value': 'active',
        'fields': ('student_state',),
        'params': {},
    },
    ('edicai.student.document', 'action_verify'): {
        'method': 'action_verify',
        'label': 'Verify document',
        'state_field': 'is_verified',
        'state_value': True,
        'fields': ('is_verified', 'verified_on'),
        'params': {'note': _note_param('verification_notes')},
    },
    ('edicai.student.document', 'action_unverify'): {
        'method': 'action_unverify',
        'label': 'Unverify document',
        'state_field': 'is_verified',
        'state_value': False,
        'fields': ('is_verified',),
        'params': {'note': _note_param('verification_notes')},
    },
    ('edicai.admission.applicant', 'action_move_to_waitlist'): {
        'method': 'action_move_to_waitlist',
        'label': 'Move to waitlist',
        'state_field': 'state',
        'state_value': 'waitlisted',
        'fields': ('state',),
        'params': {},
    },
}


def action_spec(model, action):
    """The declared spec for (model, method), or None (deny-by-default)."""
    return ENTITY_ACTIONS.get(
        (str(model or '').strip(), str(action or '').strip()))


def action_label(model, action):
    spec = action_spec(model, action)
    return spec['label'] if spec else False


def validate_action_params(spec, params):
    """Closed parameter grammar: only declared names, text, capped."""
    declared = (spec or {}).get('params') or {}
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise UserError(ERROR_ACTION_PARAMS)
    clean = {}
    for name, value in params.items():
        meta = declared.get(str(name or '').strip())
        if not meta:
            raise UserError(ERROR_ACTION_PARAMS)
        if value is None or value is False:
            continue
        if not isinstance(value, str):
            raise UserError(ERROR_ACTION_PARAMS)
        text = value.strip()
        if not text:
            continue
        if len(text) > meta['max_len']:
            raise UserError(ERROR_ACTION_PARAMS)
        clean[str(name).strip()] = text
    return clean


def run_action(record, spec, clean_params):
    """Execute ONE declared action on ONE record, as the current user.

    The method name comes from ``spec['method']`` — a literal in this
    module — never from the payload or the database. Idempotent by
    design: when the record is already in the target state nothing is
    called and ``changed`` is False.

    :returns: dict with ``changed``, ``before`` and ``after`` state.
        Raises whatever the ERP method raises (the caller classifies
        UserError/ValidationError as a retryable business rejection).
    """
    state_field = spec['state_field']
    expected = spec['state_value']
    before = getattr(record, state_field)
    if before == expected:
        return {'changed': False, 'before': before, 'after': before}
    method = getattr(record, spec['method'], None)
    if not callable(method):
        # A model that stopped providing the declared method is a code
        # drift: refuse, never guess an alternative.
        _logger.error(
            'AI entity action: declared method %s missing on %s.',
            spec['method'], record._name)
        raise UserError(ERROR_ACTION_UNAVAILABLE)
    method()
    # Declared follow-up fields (fixed target columns only — this is
    # NOT a generic write surface).
    for name, value in (clean_params or {}).items():
        target = spec['params'][name]['target']
        record.write({target: value})
    record.invalidate_recordset([state_field])
    after = getattr(record, state_field)
    return {'changed': True, 'before': before, 'after': after}
