r"""AI Generic Entity Tools — the generic layer (Phases G1/G2/G3).

Nine policy-gated capability tools replace the "one hardcoded tool per
question type" model:

=========================  ============================================
``entity.list_models``     which entities can this caller ask about
``entity.describe``        one entity's schema as the AI sees it
``entity.search``          rows by a CLOSED filter grammar
``entity.read``            named records by id (PII masked)
``entity.aggregate``       count/sum/avg/min/max grouped rows
``entity.create``          stage ONE record creation (G2, confirm)
``entity.update``          stage ONE record edit (G2, confirm)
``entity.execute``         run ONE declared record action (G3, confirm)
``entity.list_actions``    which declared actions exist (per caller)
=========================  ============================================

Every execution of the REGISTERED tools:

* resolves the entity's ``edicai.ai.entity.policy`` row (deny-by-default;
  disabled/unknown/grant-less callers are refused, never guessed);
* runs as the calling user — NO sudo, record rules always apply, so a
  policy row can never expose data the user cannot already read;
* enforces the field allow/block lists and masks PII fields;
* caps rows/payloads with the policy ``max_rows``;
* goes through ``edicai.ai.tool.registry.execute_tool`` (group gate,
  rate limit, redaction, durable audit) like every Phase tool.

Two entry paths use the same engine, both grant-checked:

* the read/staging tools above — entity-policy grant (deny-by-default);
* the Phase 13 cohort tools (``fees.fee_summary``) call the ENGINE
  internally — their callers are gated by their own registry contract;
  data scoping is identical (record rules + row caps) in both paths.

The filter grammar is CLOSED: ``[[field, op, value], ...]`` with op in
``FILTER_OPS`` and op families restricted by field type. The validator
is authoritative — an LLM proposer (Phase G4) can only emit this
grammar; anything else is refused with a sanitized error.
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.edicai_ai.models.ai_entity_actions import (
    ENTITY_ACTIONS,
    action_label,
    action_spec,
    validate_action_params,
)
from odoo.addons.edicai_ai.models.ai_pending_action import (
    ACTION_ENTITY_CREATE,
    ACTION_ENTITY_EXECUTE,
    ACTION_ENTITY_UPDATE,
)

_logger = logging.getLogger(__name__)

#: Closed filter-operator grammar (op families restricted by type).
FILTER_OPS = {
    'eq': '=', 'ne': '!=', 'in': 'in', 'not_in': 'not in',
    'like': 'like', 'ilike': 'ilike',
    'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<=',
}

#: Hard cap on the number of closed-grammar filters in ONE search
#: request (tool path AND proposal preview).
MAX_SEARCH_FILTERS = 8

#: Which operator families are valid for which field types.
_OPS_FOR = {
    'many2one': ('eq', 'ne', 'in', 'not_in'),
    'selection': ('eq', 'ne', 'in', 'not_in'),
    'boolean': ('eq', 'ne', 'in', 'not_in'),
    'integer': ('eq', 'ne', 'in', 'not_in', 'gt', 'gte', 'lt', 'lte'),
    'float': ('eq', 'ne', 'in', 'not_in', 'gt', 'gte', 'lt', 'lte'),
    'monetary': ('eq', 'ne', 'in', 'not_in', 'gt', 'gte', 'lt', 'lte'),
    'date': ('eq', 'ne', 'in', 'not_in', 'gt', 'gte', 'lt', 'lte'),
    'datetime': ('eq', 'ne', 'in', 'not_in', 'gt', 'gte', 'lt', 'lte'),
    'char': ('eq', 'ne', 'in', 'not_in', 'like', 'ilike'),
    'text': ('eq', 'ne', 'in', 'not_in', 'like', 'ilike'),
}

_ALLOWED_MEASURES = ('count', 'sum', 'avg', 'min', 'max')
_NUMERIC_TYPES = ('integer', 'float', 'monetary')

#: Simple columnar types the AI layer may touch. Binary, one2many,
#: many2many and related fields beyond these are excluded everywhere.
_SIMPLE_TYPES = ('char', 'text', 'integer', 'float', 'monetary',
                 'boolean', 'date', 'datetime', 'selection', 'many2one')

_MAX_DEFAULT_COLUMNS = 6
_MAX_GROUP_COLUMNS = 2
_HARD_ROW_CAP = 200
_DEFAULT_LIMIT = 50

READ_OPS = ('search', 'read', 'aggregate', 'describe')
MUTATION_OPS = ('create', 'update')

ERROR_UNKNOWN = (
    'This entity/model is not available to the AI layer (unknown or '
    'disabled).')
ERROR_NO_ACCESS = 'You are not allowed to use this AI operation.'
ERROR_VALIDATION = (
    'The requested filter/column combination is not allowed by the AI '
    'policy.')
ERROR_APPROVAL_REQUIRED = (
    'This action needs approval and cannot be executed through the AI '
    'layer yet.')


class EdicaiAIEntityTools(models.AbstractModel):
    """Generic, policy-gated entity read tools (Phase G1)."""

    _name = 'edicai.ai.entity.tools'
    _description = 'AI Generic Entity Tools (read floor, policy-gated)'

    # ------------------------------------------------------------------
    # Policy resolution + grants (deny-by-default, no sudo)
    # ------------------------------------------------------------------

    def _require(self, model_ref, op):
        """(policy row, model env) or UserError; sanitized messages."""
        Policy = self.env['edicai.ai.entity.policy']
        policy = Policy.policy_for(model_ref, op)
        if not policy or not policy.exists():
            raise UserError(ERROR_UNKNOWN)
        # G2/G3: create/update grant via write_groups, execute via
        # execute_groups (deny-by-default: both columns are EMPTY on a
        # seeded entity until a manager deliberately opens them).
        # Reads grant via read_groups.
        if op in MUTATION_OPS:
            grant_column = 'write_groups'
        elif op == 'execute':
            grant_column = 'execute_groups'
        else:
            grant_column = 'read_groups'
        if not policy.caller_has_group(grant_column, self.env.user):
            raise UserError(ERROR_NO_ACCESS)
        if model_ref not in self.env:
            raise UserError(ERROR_UNKNOWN)
        return policy

    # ------------------------------------------------------------------
    # Field visibility
    # ------------------------------------------------------------------

    def _holds_any_group(self, groups_value, user):
        entries = groups_value
        if isinstance(entries, str):
            entries = [part for part in entries.split(',') if part]
        for entry in entries:
            try:
                if user.has_group(entry):
                    return True
            except Exception:
                continue
        return False

    def _fields_meta(self, model_env, policy, user):
        """Visible simple fields: type-checked, block/allow-listed and
        per-field-group filtered (a field the caller cannot read is
        excluded — including 'groups'-restricted columns). Empty policy
        = no allow/block lists apply (all simple fields visible)."""
        allowlist = policy._csv('field_allow') if policy is not None \
            else ()
        blocklist = policy._csv('field_block') if policy is not None \
            else ()
        visible = {}
        for name, meta in model_env.fields_get().items():
            if name.startswith('__'):
                continue
            if meta.get('type') not in _SIMPLE_TYPES:
                continue
            if name in blocklist:
                continue
            if allowlist and name not in allowlist:
                continue
            groups = meta.get('groups')
            if groups and not self._holds_any_group(groups, user):
                continue
            visible[name] = meta
        return visible

    def _default_columns(self, visible):
        preferred = (
            ['name'] if 'name' in visible else
            ['display_name'] if 'display_name' in visible else [])
        columns = list(preferred)
        columns += [
            f for f in sorted(visible)
            if f not in columns
        ][:(_MAX_DEFAULT_COLUMNS - len(columns))]
        return columns

    def _masked(self, name, value, policy):
        """PII masking: '***' keeps only the last 2 characters."""
        if policy is not None:
            if name in policy._csv('pii_fields') and value:
                value = str(value)
                if len(value) <= 2:
                    return '***'
                return '*' * (len(value) - 2) + value[-2:]
        return value

    # ------------------------------------------------------------------
    # G2 — mutation validation (shared by the tools AND the
    # pending-action executor: every rule runs twice, at preview AND
    # at confirm time)
    # ------------------------------------------------------------------

    #: Never AI-writable, whatever the entity policy says (identity and
    #: multi-tenant isolation are server-owned concerns).
    _NEVER_WRITABLE = ('id', 'company_id', 'create_uid', 'write_uid',
                       'create_date', 'write_date')

    def _writable_fields(self, model_env, policy):
        """AI-writable fields: simple types, not block-listed, not
        readonly/computed (deny-by-default: computed values belong to
        the ERP state machine, never to the AI layer)."""
        writable = {}
        for name, meta in self._fields_meta(
                model_env, policy, self.env.user).items():
            if name in self._NEVER_WRITABLE:
                continue
            if meta.get('readonly') or meta.get('compute'):
                continue
            writable[name] = meta
        return writable

    def _coerce_value(self, meta, value):
        """Coerce + type-check ONE field value for the write path."""
        ftype = meta.get('type')
        if ftype == 'boolean':
            if not isinstance(value, bool):
                raise UserError(ERROR_VALIDATION)
            return value
        if ftype == 'integer':
            if isinstance(value, bool) or not isinstance(value, int):
                raise UserError(ERROR_VALIDATION)
            return value
        if ftype in ('float', 'monetary'):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise UserError(ERROR_VALIDATION)
            return float(value)
        if ftype == 'many2one':
            if isinstance(value, bool) or value is False or value is None:
                return False
            if not isinstance(value, int) or value <= 0:
                raise UserError(ERROR_VALIDATION)
            return value
        if ftype == 'selection':
            keys = [k for k, _v in (meta.get('selection') or [])]
            if value not in keys:
                raise UserError(ERROR_VALIDATION)
            return value
        if ftype in ('date', 'datetime'):
            if not isinstance(value, str) or not value.strip():
                raise UserError(ERROR_VALIDATION)
            try:
                if ftype == 'date':
                    return str(fields.Date.to_date(value.strip()))
                return str(fields.Datetime.to_datetime(value.strip()))
            except Exception:
                raise UserError(ERROR_VALIDATION)
        if ftype in ('char', 'text'):
            if not isinstance(value, (str, int, float)):
                raise UserError(ERROR_VALIDATION)
            text = str(value).strip()
            cap = meta.get('size') or 4096
            if len(text) > cap:
                raise UserError(ERROR_VALIDATION)
            return text
        # every other columnar type (binary, relational lists,
        # json...) is NOT technology the AI layer may write.
        raise UserError(ERROR_VALIDATION)

    def authorize_entity_mutation(self, model, op):
        """Reason-coded POLICY decision for a create/update op.

        Shared by the staging tools AND the pending-action executor:
        the same entity-policy grant re-checks at preview and at
        confirm time. Never raises; returns a decision dict.
        """
        policy = self.env['edicai.ai.entity.policy'].policy_for(
            model, op)
        if not policy or not policy.exists():
            return {'ok': False, 'reason_code': 'ENTITY_UNKNOWN'}
        if not policy.caller_has_group(
                'write_groups', self.env.user):
            return {'ok': False, 'reason_code': 'ENTITY_WRITE_GROUPS'}
        return {'ok': True, 'reason_code': 'OK', 'policy': policy}

    def validate_mutation_values(self, model, values, op):
        """Validate a create/update payload against the entity policy.

        Deny-by-default at every layer: policy row must exist and list
        the op; the caller must hold a write_groups group; only
        writable fields pass through; required fields must be present
        for create. Raw values are COERCED — the executor writes only
        what this function returns.
        """
        if op not in MUTATION_OPS:
            raise UserError(ERROR_NO_ACCESS)
        auth = self.authorize_entity_mutation(model, op)
        if not auth['ok']:
            raise UserError(ERROR_NO_ACCESS)
        policy = auth['policy']
        if model not in self.env:
            raise UserError(ERROR_UNKNOWN)
        model_env = self.env[model]
        writable = self._writable_fields(model_env, policy)
        if not isinstance(values, dict) or not values:
            raise UserError(ERROR_VALIDATION)
        clean = {}
        for name, value in values.items():
            name = str(name or '').strip()
            meta = writable.get(name)
            if not meta:
                raise UserError(ERROR_VALIDATION)
            clean[name] = self._coerce_value(meta, value)
        if op == 'create':
            missing = [
                name for name, meta in writable.items()
                if meta.get('required') and not clean.get(name)
                # a defaulted required field is legitimately omitted —
                # the server default stays authoritative (fields_get
                # does not expose 'default' in Odoo 19; read the field)
                and model_env._fields[name].default is None
            ]
            if missing:
                raise UserError(ERROR_VALIDATION)
        return clean

    # ------------------------------------------------------------------
    # G2 — entity.create / entity.update (confirm flow ONLY)
    # ------------------------------------------------------------------

    def _confirm_session(self, params):
        """Owner-bound chat session for the pending action row."""
        sid = (params or {}).get('session_id')
        if isinstance(sid, bool) or not isinstance(sid, int) or sid <= 0:
            raise UserError(ERROR_VALIDATION)
        session = self.env['edicai.ai.chat.session'].browse(sid)
        # check_access applies ACL AND record rules: a session owned by
        # somebody else is DENIED here (never a raw AccessError leak).
        try:
            session.check_access('read')
        except Exception:
            raise UserError(ERROR_NO_ACCESS)
        if not session.exists():
            raise UserError(ERROR_UNKNOWN)
        if session.user_id.id != self.env.user.id:
            raise UserError(ERROR_NO_ACCESS)
        return session

    def _entity_pending_reply(self, row, superseded, action):
        payload = row._read_payload()
        reply = {
            'action': action,
            'pending_id': row.id,
            'pending_ref': row.ref,
            'requires_confirmation': True,
            'model': payload.get('model'),
            'superseded': bool(superseded),
            'status': row.status,
        }
        if payload.get('entity_action'):
            reply['entity_action'] = payload['entity_action']
            reply['action_label'] = action_label(
                payload.get('model'), payload['entity_action'])
        return reply

    def tool_entity_create(self, params=None):
        """Plan a generic record CREATE.

        NEVER writes business data: validates (policy write grant,
        writable fields, types, required) and stages ONE
        ``edicai.ai.pending.action`` (supersede on material change).
        Execution happens ONLY at confirm time, as the confirming
        user (record rules + ACL re-enforced there).
        """
        params = params or {}
        model = str(params.get('model') or '').strip()
        session = self._confirm_session(params)
        self._require(model, 'create')
        clean = self.validate_mutation_values(
            model, params.get('values'), 'create')
        Pending = self.env['edicai.ai.pending.action']
        previous = Pending.open_active(session, self.env.user)
        row = Pending.create_pending(
            session, {'model': model, 'values': clean},
            action=ACTION_ENTITY_CREATE)
        superseded = bool(previous) and previous.id != row.id
        row.mark_preview()
        return self._entity_pending_reply(row, superseded,
                                          'entity.create')

    def tool_entity_update(self, params=None):
        """Plan a generic record UPDATE (same lifecycle as create)."""
        params = params or {}
        model = str(params.get('model') or '').strip()
        session = self._confirm_session(params)
        self._require(model, 'update')
        record_id = params.get('record_id')
        if isinstance(record_id, bool) or not isinstance(
                record_id, int) or record_id <= 0:
            raise UserError(ERROR_VALIDATION)
        clean = self.validate_mutation_values(
            model, params.get('values'), 'update')
        model_env = self.env[model]
        record = model_env.browse(record_id)
        try:
            record.check_access('read')
        except Exception:
            raise UserError(ERROR_NO_ACCESS)
        if not record.exists():
            raise UserError(ERROR_VALIDATION)
        Pending = self.env['edicai.ai.pending.action']
        previous = Pending.open_active(session, self.env.user)
        row = Pending.create_pending(
            session,
            {'model': model, 'values': clean,
             'record_id': record_id},
            action=ACTION_ENTITY_UPDATE)
        superseded = bool(previous) and previous.id != row.id
        row.mark_preview()
        return self._entity_pending_reply(row, superseded,
                                          'entity.update')

    # ------------------------------------------------------------------
    # G3 — entity.execute (declared record actions, confirm flow ONLY)
    # ------------------------------------------------------------------

    def _action_row(self, model, action):
        return self.env['edicai.ai.entity.action'].search([
            ('model_ref', '=', model),
            ('action', '=', action),
            ('enabled', '=', True),
        ], limit=1)

    def authorize_entity_execute(self, model, action):
        """Reason-coded POLICY decision for ONE declared record action.

        Two independent gates, both deny-by-default:

        * DATA — the entity policy lists ``execute`` AND the caller
          holds ``execute_groups``, AND an enabled action row for the
          (model, method) pair whose ``allowed_groups`` the caller
          holds;
        * CODE — the pair exists in ``ai_entity_actions.ENTITY_ACTIONS``
          (a data row can never expose an arbitrary ORM method).

        Never raises; never echoes the payload.
        """
        policy = self.env['edicai.ai.entity.policy'].policy_for(
            model, 'execute')
        if not policy or not policy.exists():
            return {'ok': False, 'reason_code': 'ENTITY_UNKNOWN'}
        if not policy.caller_has_group(
                'execute_groups', self.env.user):
            return {'ok': False, 'reason_code': 'ENTITY_EXECUTE_GROUPS'}
        row = self._action_row(model, action)
        if not row:
            return {'ok': False, 'reason_code': 'ENTITY_ACTION_UNKNOWN'}
        if not self._holds_any_group(
                row.allowed_groups or (), self.env.user):
            return {'ok': False, 'reason_code': 'ENTITY_ACTION_GROUPS'}
        if row.needs_approval:
            # Entity actions are NOT wired into the Phase 4 approval
            # lane yet: an approval-required action is refused, never
            # silently treated as approved.
            return {'ok': False, 'reason_code': 'APPROVAL_REQUIRED'}
        if not action_spec(model, action):
            # The belt (data) cannot widen the braces (code).
            return {'ok': False, 'reason_code': 'ENTITY_ACTION_NO_CODE'}
        if model not in self.env:
            return {'ok': False, 'reason_code': 'ENTITY_UNKNOWN'}
        return {'ok': True, 'reason_code': 'OK', 'policy': policy}

    def validate_execute_params(self, model, action, params):
        """Closed parameter grammar of ONE declared action."""
        spec = action_spec(model, action)
        if not spec:
            raise UserError(ERROR_NO_ACCESS)
        return validate_action_params(spec, params)

    def tool_entity_execute(self, params=None):
        """Plan ONE declared record action.

        NEVER executes at call time: validates (entity execute grant,
        action row + groups, code registry, closed params, record
        readable by the caller) and stages ONE
        ``edicai.ai.pending.action``. The ERP method runs only in
        ``confirm_and_execute``, as the confirming user.
        """
        params = params or {}
        model = str(params.get('model') or '').strip()
        action = str(params.get('action') or '').strip()
        session = self._confirm_session(params)
        auth = self.authorize_entity_execute(model, action)
        if not auth['ok']:
            if auth['reason_code'] == 'APPROVAL_REQUIRED':
                raise UserError(ERROR_APPROVAL_REQUIRED)
            raise UserError(ERROR_NO_ACCESS)
        record_id = params.get('record_id')
        if isinstance(record_id, bool) or not isinstance(
                record_id, int) or record_id <= 0:
            raise UserError(ERROR_VALIDATION)
        clean = self.validate_execute_params(
            model, action, params.get('params'))
        record = self.env[model].browse(record_id)
        try:
            record.check_access('read')
        except Exception:
            raise UserError(ERROR_NO_ACCESS)
        if not record.exists():
            raise UserError(ERROR_VALIDATION)
        Pending = self.env['edicai.ai.pending.action']
        previous = Pending.open_active(session, self.env.user)
        row = Pending.create_pending(
            session,
            {'model': model, 'entity_action': action,
             'record_id': record_id, 'params': clean},
            action=ACTION_ENTITY_EXECUTE)
        superseded = bool(previous) and previous.id != row.id
        row.mark_preview()
        return self._entity_pending_reply(row, superseded,
                                          'entity.execute')

    # ------------------------------------------------------------------
    # G2/G3 — entity.list_actions (the whitelisted method table)
    # ------------------------------------------------------------------

    def tool_list_actions(self, params=None):
        """Which whitelisted ACTIONS exist (per model, grant-filtered)."""
        params = params or {}
        model = str(params.get('model') or '').strip()
        domain = [('enabled', '=', True)]
        if model:
            domain.append(('model_ref', '=', model))
        rows = []
        for row in self.env['edicai.ai.entity.action'].search(
                domain, order='model_ref,action'):
            groups_value = row.allowed_groups
            if not self._holds_any_group(
                    groups_value if groups_value else (), self.env.user):
                continue
            auth = self.authorize_entity_execute(
                row.model_ref, row.action)
            rows.append({
                'model': row.model_ref,
                'action': row.action,
                'label': row.label or action_label(
                    row.model_ref, row.action) or row.action,
                'needs_approval': bool(row.needs_approval),
                # Honest signal: would THIS caller be allowed to stage
                # it right now? (flag + policy + grant + code registry)
                'executable': bool(auth['ok']),
                'reason_code': auth['reason_code'],
            })
        return {'actions': rows, 'count': len(rows)}

    # ------------------------------------------------------------------
    # Closed filter grammar
    # ------------------------------------------------------------------

    def _build_domain(self, model_env, raw_filters):
        meta_all = model_env.fields_get()
        domain = []
        for entry in (raw_filters or []):
            domain.append(self._compile_filter(model_env, entry))
        if 'company_id' in meta_all and meta_all['company_id'].get(
                'store', True):
            domain.append(('company_id', '=', self.env.company.id))
        return domain

    def _compile_filter(self, model_env, entry):
        """Validate ONE closed-grammar filter entry against the model.

        Shared: the tool path (``_build_domain``) and the G4 proposal
        preview run EXACTLY this check — the LLM can never widen the
        grammar. Raises UserError for ANY violation.
        """
        meta_all = model_env.fields_get()
        if not isinstance(entry, (list, tuple)) or len(entry) != 3:
            raise UserError(ERROR_VALIDATION)
        field, op, value = entry
        field = str(field or '').strip()
        if '.' in field:
            # Relational paths (campus_id.id) are closed joins —
            # never allowed through the AI layer.
            raise UserError(ERROR_VALIDATION)
        op = str(op or '').strip().lower()
        if op not in FILTER_OPS:
            raise UserError(ERROR_VALIDATION)
        meta = meta_all.get(field)
        if not meta or meta.get('type') not in _OPS_FOR:
            raise UserError(ERROR_VALIDATION)
        # Non-stored computed columns cannot enter SQL where
        # clauses (e.g. is_overdue); refusing them up front also
        # blocks non-deterministic filters.
        if not meta.get('store', True):
            raise UserError(ERROR_VALIDATION)
        if op not in _OPS_FOR[meta['type']]:
            raise UserError(ERROR_VALIDATION)
        if meta['type'] == 'many2one' and isinstance(value, str):
            # m2o comparisons accept ids (plus False), never names
            # (name resolution is the LLM's job in G4 via search).
            raise UserError(ERROR_VALIDATION)
        if isinstance(value, str) and '\x00' in value:
            raise UserError(ERROR_VALIDATION)
        if isinstance(value, (list, tuple)):
            value = list(value)
        return (field, FILTER_OPS[op], value)

    def preview_search_params(self, params):
        """Validate ONE ``entity.search`` request WITHOUT executing it.

        G4: the conversational proposal layer calls this so an LLM
        proposal is deterministically re-validated against the SAME
        closed grammar + the caller's grants (deny-by-default) BEFORE
        anything routes. Runs as the calling user — no sudo. Any
        violation returns ``None`` (fail-closed), never repairs.

        :returns: normalized params dict (model/label/filters/fields/
            order/limit) or ``None`` when the request is invalid or
            not granted for this caller.
        """
        params = params or {}
        model = str(params.get('model') or '').strip()
        try:
            policy = self._require(model, 'search')
            model_env = self.env[model]
            visible = self._fields_meta(model_env, policy, self.env.user)
            raw_filters = params.get('filters')
            if raw_filters is None:
                raw_filters = []
            if not isinstance(raw_filters, list) \
                    or len(raw_filters) > MAX_SEARCH_FILTERS:
                return None
            # Validate through the SAME compiler the tool uses, but
            # return the normalized SYMBOLIC form ([field, op, value]):
            # ``tool_search`` re-compiles at execution, so handing it
            # already-compiled domains would be a second, invalid pass.
            filters = []
            for entry in raw_filters:
                field, _odoo_op, value = self._compile_filter(
                    model_env, entry)
                filters.append([
                    field,
                    str(entry[1] or '').strip().lower(),
                    value,
                ])
            order = self._validate_order(visible, params.get('order'))
            limit = self._cap(policy, params.get('limit'))
            columns = self._columns_param(
                {'fields': params.get('fields') or ''}, visible)
        except Exception:  # noqa: BLE001 — fail-closed by design
            return None
        return {
            'model': policy.model_ref,
            'label': policy.label,
            'filters': filters,
            'fields': ','.join(columns),
            'order': order or '',
            'limit': int(limit),
        }

    def _validate_order(self, visible, order):
        tokens = []
        for token in str(order or '').split(','):
            token = token.strip()
            if not token:
                continue
            parts = token.split()
            name = parts[0]
            direction = (parts[1].lower() if len(parts) > 1 else '')
            if name not in visible or direction not in ('', 'asc', 'desc'):
                raise UserError(ERROR_VALIDATION)
            tokens.append('%s %s' % (name, direction) if direction
                          else name)
        return ' '.join(tokens)

    def _cap(self, policy, limit):
        try:
            limit = int(limit or _DEFAULT_LIMIT)
        except (TypeError, ValueError):
            limit = _DEFAULT_LIMIT
        cap = policy.max_rows if policy is not None else 0
        return max(1, min(limit, _HARD_ROW_CAP, cap or 100))

    def _columns_param(self, params, visible):
        requested = [
            f.strip()
            for f in str((params or {}).get('fields') or '').split(',')
            if f.strip()
        ]
        if requested:
            columns = [f for f in requested if f in visible]
            if not columns:
                raise UserError(ERROR_VALIDATION)
            return columns
        return self._default_columns(visible)

    # ------------------------------------------------------------------
    # Tool 1: entity.list_models
    # ------------------------------------------------------------------

    def tool_list_models(self, params=None):
        """Which entities may this caller ask about (labels + ops)."""
        params = params or {}
        query = str(params.get('query') or '').strip().lower()
        rows = []
        for policy in self.env['edicai.ai.entity.policy'].search(
                [], order='model_ref'):
            if not policy.enabled:
                continue
            if not policy.caller_has_group('read_groups', self.env.user):
                continue
            labels = [policy.label or ''] + list(policy._csv('synonyms'))
            if query and not any(
                    query in (label or '').lower() for label in labels):
                continue
            rows.append({
                'model': policy.model_ref,
                'label': policy.label,
                'ops': list(policy._ops_list()),
                'synonyms': list(policy._csv('synonyms')),
            })
        return {
            'entities': rows,
            'count': len(rows),
            'query': query or False,
        }

    # ------------------------------------------------------------------
    # Tool 2: entity.describe
    # ------------------------------------------------------------------

    def tool_describe(self, params=None):
        """One entity's schema: fields, types, required, PII flags."""
        model = str((params or {}).get('model') or '').strip()
        policy = self._require(model, 'describe')
        user = self.env.user
        visible = self._fields_meta(self.env[model], policy, user)

        fields_out = []
        blocked = policy._csv('field_block')
        for name, meta in sorted(visible.items()):
            entry = {
                'name': name,
                'label': meta.get('string'),
                'type': meta.get('type'),
                'required': bool(meta.get('required')),
                'pii': name in policy._csv('pii_fields'),
                'write_blocked': name in blocked,
            }
            if meta.get('selection'):
                entry['selection'] = [k for k, _v in meta['selection']]
            if meta.get('type') == 'many2one':
                entry['comodel'] = meta.get('relation')
            fields_out.append(entry)
        return {
            'model': policy.model_ref,
            'label': policy.label,
            'ops': {
                'read': policy.caller_has_group('read_groups', user),
                'write': policy.caller_has_group('write_groups', user),
                'delete': policy.caller_has_group('delete_groups', user),
            },
            'row_cap': policy.max_rows,
            'fields': fields_out,
            'field_count': len(fields_out),
        }

    # ------------------------------------------------------------------
    # Tool 3: entity.search
    # ------------------------------------------------------------------

    def tool_search(self, params=None):
        """Records by the closed filter grammar (record rules apply)."""
        params = params or {}
        model = str(params.get('model') or '').strip()
        policy = self._require(model, 'search')
        model_env = self.env[model]
        visible = self._fields_meta(model_env, policy, self.env.user)

        domain = self._build_domain(model_env, params.get('filters'))
        order = self._validate_order(visible, params.get('order'))
        limit = self._cap(policy, params.get('limit'))

        total = model_env.search_count(domain)
        records = model_env.search(
            domain, order=order or None, limit=limit)
        columns = self._columns_param(params, visible)

        rows = []
        for record in records:
            row = {'id': record.id}
            for column in columns:
                raw = getattr(record, column)
                if isinstance(raw, models.BaseModel):
                    raw = raw.display_name
                row[column] = self._masked(column, raw, policy)
            rows.append(row)
        return {
            'model': policy.model_ref,
            'label': policy.label,
            'count': len(rows),
            'total_in_scope': total,
            'truncated': total > len(rows),
            'row_cap': limit,
            'fields': columns,
            'rows': rows,
        }

    # ------------------------------------------------------------------
    # Tool 4: entity.read
    # ------------------------------------------------------------------

    def tool_read(self, params=None):
        """Read named records by id (PII masked, row cap enforced)."""
        params = params or {}
        model = str(params.get('model') or '').strip()
        policy = self._require(model, 'read')
        model_env = self.env[model]
        visible = self._fields_meta(model_env, policy, self.env.user)

        raw_ids = params.get('ids') or params.get('id')
        if isinstance(raw_ids, int):
            raw_ids = [raw_ids]
        if not isinstance(raw_ids, list) or not raw_ids:
            raise UserError(ERROR_VALIDATION)
        ids = []
        for value in raw_ids:
            if isinstance(value, bool) or not isinstance(value, int) \
                    or value <= 0:
                raise UserError(ERROR_VALIDATION)
            ids.append(value)
        ids = ids[:self._cap(policy, len(ids))]

        records = model_env.browse(ids)
        try:
            records.check_access('read')
        except Exception:
            raise UserError(ERROR_NO_ACCESS)
        records = records.exists()
        columns = self._columns_param(params, visible)

        rows = []
        for record in records:
            row = {'id': record.id}
            for column in columns:
                raw = getattr(record, column)
                if isinstance(raw, models.BaseModel):
                    raw = raw.display_name
                row[column] = self._masked(column, raw, policy)
            rows.append(row)
        return {
            'model': policy.model_ref,
            'label': policy.label,
            'count': len(rows),
            'row_cap': len(ids),
            'fields': columns,
            'rows': rows,
        }

    # ------------------------------------------------------------------
    # Tool 5: entity.aggregate (grants) + the shared engine
    # ------------------------------------------------------------------

    def aggregate_for_policy(self, model, filters=None, group_by=None,
                             measures=None, group_limit=None):
        """Shared INTERNAL aggregate engine.

        No entity-grant checks here — see the module docstring. Record
        rules, row caps, the closed filter grammar and the field
        allow/block lists ALWAYS apply; a caller without a valid
        registered path simply does not reach this method.
        """
        if model not in self.env:
            raise UserError(ERROR_UNKNOWN)
        policy = self.env['edicai.ai.entity.policy'].policy_for(
            model, 'aggregate')
        model_env = self.env[model]
        visible = self._fields_meta(model_env, policy, self.env.user)

        group_by_raw = group_by or 'id'
        if isinstance(group_by_raw, str):
            group_by_raw = [group_by_raw]
        if not isinstance(group_by_raw, list) or not (
                1 <= len(group_by_raw) <= _MAX_GROUP_COLUMNS):
            raise UserError(ERROR_VALIDATION)
        group_by = []
        for field in group_by_raw:
            field = str(field or '').strip()
            meta = visible.get(field)
            if not meta or not meta.get('store', True):
                raise UserError(ERROR_VALIDATION)
            group_by.append(field)

        domain = self._build_domain(model_env, filters)

        if not isinstance(measures, dict):
            measures = {}
        aggregate_specs, aggregate_names = [], []
        for field, agg in measures.items():
            field = str(field or '').strip()
            agg = str(agg or '').strip().lower()
            if agg not in _ALLOWED_MEASURES:
                raise UserError(ERROR_VALIDATION)
            if agg == 'count':
                aggregate_specs.append('__count')
                aggregate_names.append('__count')
                continue
            if field not in visible \
                    or not visible[field].get('store', True) \
                    or visible[field]['type'] not in _NUMERIC_TYPES:
                raise UserError(ERROR_VALIDATION)
            aggregate_specs.append('%s:%s' % (field, agg))
            aggregate_names.append('%s:%s' % (field, agg))
        if not aggregate_specs:
            aggregate_specs, aggregate_names = ['__count'], ['__count']

        total = model_env.search_count(domain)
        group_cap = self._cap(policy, group_limit)
        if total:
            raw_rows = model_env._read_group(
                domain=domain,
                groupby=group_by,
                aggregates=aggregate_specs,
                limit=group_cap,
            )
        else:
            raw_rows = []

        rows = []
        for row in raw_rows:
            entry = {}
            for i, field in enumerate(group_by):
                value = row[i]
                # Odoo 19 _read_group returns many2one groups as RECORDSETS
                # of the comodel (17- returned (id, label) tuples).
                if isinstance(value, models.BaseModel):
                    label = False
                    try:
                        label = value.display_name
                    except Exception:
                        pass
                    entry[field] = (label
                                    or ('(id %s)' % value.id
                                        if value.id else False))
                elif isinstance(value, tuple) and len(value) == 2:
                    entry[field] = (value[1] or '(id %s)' % value[0])
                else:
                    entry[field] = value if value is not None else False
            for i, name in enumerate(aggregate_names):
                value = row[len(group_by) + i]
                if isinstance(value, float):
                    value = round(value, 2)
                entry[name] = value
            rows.append(entry)
        rows.sort(key=lambda e: e.get('__count') or 0, reverse=True)
        return {
            'model': model,
            'group_by': group_by,
            'total_records': total,
            'count': len(rows),
            'rows': rows,
            'row_cap': group_cap,
            'empty': not total,
        }

    def tool_aggregate(self, params=None):
        """Grouped cohort numbers — the policy-gated HOW MANY tool."""
        params = params or {}
        model = str(params.get('model') or '').strip()
        policy = self._require(model, 'aggregate')
        result = self.aggregate_for_policy(
            model,
            filters=params.get('filters'),
            group_by=params.get('group_by'),
            measures=params.get('measures'),
            group_limit=params.get('group_limit'),
        )
        result['label'] = policy.label
        return result


# ---------------------------------------------------------------------------
# Self-registration (restart-resilient, mirrors ai_tools_conversational)
# ---------------------------------------------------------------------------


#: G1 read floor + G2/G3 mutation surface (mutations NEVER write at
#: call time — they stage a pending action; the confirm flow executes).
_ENTITY_TOOL_NAMES = (
    'entity.list_models',
    'entity.describe',
    'entity.search',
    'entity.read',
    'entity.aggregate',
    'entity.create',
    'entity.update',
    'entity.execute',
    'entity.list_actions',
)

_ENTITY_TOOL_METHODS = {
    'entity.list_models': 'tool_list_models',
    'entity.describe': 'tool_describe',
    'entity.search': 'tool_search',
    'entity.read': 'tool_read',
    'entity.aggregate': 'tool_aggregate',
    'entity.create': 'tool_entity_create',
    'entity.update': 'tool_entity_update',
    'entity.execute': 'tool_entity_execute',
    'entity.list_actions': 'tool_list_actions',
}

_ENTITY_TOOL_SPECS = {
    'entity.create': {'risk_level': 'MUTATION',
                      'rate_limit_per_hour': 20, 'phase': 'G2'},
    'entity.update': {'risk_level': 'MUTATION',
                      'rate_limit_per_hour': 20, 'phase': 'G2'},
    'entity.execute': {'risk_level': 'MUTATION',
                       'rate_limit_per_hour': 20, 'phase': 'G3'},
    'entity.list_actions': {'risk_level': 'READ_ONLY',
                            'rate_limit_per_hour': 60, 'phase': 'G2'},
}


def _register_entity_tools():
    try:
        from odoo.addons.edicai_ai.models.ai_tool_registry import (
            register_tool,
        )
    except Exception:
        _logger.exception(
            'AI entity tools: registry import failed; tools stay '
            'unregistered and every call is rejected safely.')
        return
    for name in _ENTITY_TOOL_NAMES:
        extra = _ENTITY_TOOL_SPECS.get(name, {})
        register_tool({
            'name': name,
            'kind': 'tool',
            'description': (
                'Phase G%s generic %s tool (%s) — policy-gated by '
                'edicai.ai.entity.policy; no sudo, record rules apply.'
            ) % (extra.get('phase', 'G1'),
                 extra.get('risk_level', 'READ_ONLY'), name),
            'model': 'edicai.ai.entity.tools',
            'method': _ENTITY_TOOL_METHODS[name],
            'allowed_groups': ['edicai_ai.group_edicai_ai_user'],
            'rate_limit_per_hour': extra.get('rate_limit_per_hour', 120),
            'risk_level': extra.get('risk_level', 'READ_ONLY'),
            'phase': extra.get('phase', 'G1'),
        })
    _logger.info(
        'AI entity tools: registered the G1 read floor + G2 mutation '
        'surface (create/update stage pending actions only).')


_register_entity_tools()
