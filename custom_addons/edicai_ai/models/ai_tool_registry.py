"""Central AI tool registry + scoped, audited tool execution.

All cross-module AI tools (Ask-Data intents, copilot helpers, and any
tool owned by another ``edicai_*`` module) must be registered here by
*name*.  Nothing executes unless its name is present in ``TOOL_REGISTRY``
(allow-list enforcement).

Scope injection: every execution is forced through the requester's
company (``env.company``).  A caller-supplied ``company_id`` is
overwritten, never trusted, so one institution can never read another's
data through a tool.  ``campus_id`` is passed through when supplied
(handlers apply it only if their underlying source has the field; most
analytics VIEWs are company-scoped).

Audit: every call (allowed or denied) is logged best-effort to the
first existing AI operation/request log model
(``edicai.ai.operation.log`` / ``edicai.ai.request.log``), else to
``ir.logging``.  Audit failures are swallowed (logged to the Odoo log)
so auditing can never crash a tool call.

Rate limit: per (tool, user, rolling hour) counter.  Limits come from
the tool spec, else ``ir.config_parameter`` ``edicai_ai.tool_rate_limit_default``,
else 60/hour.  The bucket is in-memory (approximate across workers);
documented as such — reuse of the API-key quota pattern was considered
but ``edicai_ai`` stores only a single key with no quota fields, so an
in-memory bucket is used instead.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

#: Allow-list: tool/role name -> spec dict.  Populated by
#: ``register_tool`` (Python API + ``data/ai_registry_data.xml``).
TOOL_REGISTRY = {}

#: (tool_name, user_id, hour_bucket) -> list[epoch seconds of calls].
_RATE_BUCKETS = defaultdict(list)

_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.]*$')
DEFAULT_RATE_LIMIT_PER_HOUR = 60
RATE_LIMIT_PARAM = 'edicai_ai.tool_rate_limit_default'

#: AI audit models, probed in order.  Neither exists in ``edicai_ai`` today;
#: the probe keeps this working if a future module adds one.
AUDIT_LOG_MODELS = (
    'edicai.ai.operation.log',
    'edicai.ai.request.log',
)

_SENSITIVE_KEYS = ('password', 'token', 'secret', 'api_key', 'apikey')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_tool(spec):
    """Register (or re-register) one tool/role spec in the allow-list.

    ``spec`` is a plain dict so it can be passed from XML data files::

        {
            'name': 'ask_data.enrollment',   # required, unique
            'kind': 'tool',                  # 'tool' (default) or 'role'
            'description': '...',
            # for kind == 'tool': dispatch target
            'model': 'edicai.ai.ask.data',
            'method': 'run_intent',
            'default_intent': 'enrollment',  # optional preset params
            # for kind == 'role': tools this copilot may call (by name;
            # the owning modules register the actual tools — no import)
            'allowed_tools': ['ask_data.enrollment', ...],
            'allowed_groups': ['edicai_ai.group_edicai_ai_user'],
            'rate_limit_per_hour': 60,
        }

    Re-registering the same name overwrites it (idempotent upgrades).
    """
    if not isinstance(spec, dict):
        raise UserError(_('Tool spec must be a dictionary.'))
    name = spec.get('name')
    if not name or not _IDENTIFIER_RE.match(name):
        raise UserError(_('Tool spec needs a valid dotted name.'))
    kind = spec.get('kind', 'tool')
    if kind not in ('tool', 'role'):
        raise UserError(_('Tool kind must be "tool" or "role".'))
    if kind == 'tool' and (not spec.get('model') or not spec.get('method')):
        raise UserError(_('Tool "%s" needs "model" and "method".') % name)
    if name in TOOL_REGISTRY:
        _logger.warning('AI tool registry: re-registering "%s".', name)
    TOOL_REGISTRY[name] = dict(spec)
    _logger.info('AI tool registry: registered "%s" (%s).', name, kind)
    return True


# ---------------------------------------------------------------------------
# Helpers: rate limit / scope / audit
# ---------------------------------------------------------------------------

def _rate_limit_for(env, spec):
    """Resolve the hourly call budget for a tool spec."""
    if spec.get('rate_limit_per_hour'):
        try:
            return max(1, int(spec['rate_limit_per_hour']))
        except (TypeError, ValueError):
            pass
    try:
        return max(1, int(env['ir.config_parameter'].sudo().get_param(
            RATE_LIMIT_PARAM, default=str(DEFAULT_RATE_LIMIT_PER_HOUR))))
    except Exception:
        return DEFAULT_RATE_LIMIT_PER_HOUR


def _check_rate_limit(env, name, user, spec):
    """Raise ``UserError`` when the (tool, user, rolling hour) budget is spent."""
    limit = _rate_limit_for(env, spec)
    now = datetime.now(timezone.utc).timestamp()
    hour = datetime.now(timezone.utc).strftime('%Y%m%d%H')
    key = (name, user.id, hour)
    bucket = [ts for ts in _RATE_BUCKETS[key] if now - ts < 3600]
    if len(bucket) >= limit:
        raise UserError(_(
            'AI tool "%(tool)s" rate limit exceeded '
            '(%(limit)s calls/hour). Please try again later.',
            tool=name, limit=limit))
    bucket.append(now)
    _RATE_BUCKETS[key] = bucket


def _redact_params(params):
    """Return a log-safe copy of params (secrets replaced)."""
    clean = {}
    for key, value in (params or {}).items():
        lowered = str(key).lower()
        if any(word in lowered for word in _SENSITIVE_KEYS):
            clean[key] = '***'
        else:
            clean[key] = value
    return clean


def _write_audit(env, tool_name, user, params, status, detail=''):
    """Best-effort audit write.  Never raises.

    Tries the known AI operation/request log models (field-filtered, so
    partial schemas still work), else falls back to ``ir.logging``.
    """
    try:
        company_id = (params or {}).get('company_id') or env.company.id
        # Phase 0 — durable audit via ``edicai.ai.audit.event`` (added by
        # edicai_ai).  Explicit mapping, backward-compatible: when the
        # model is absent the legacy probe loop / ir.logging fallback
        # below behaves exactly as before.
        if 'edicai.ai.audit.event' in env:
            try:
                event_type = {'ok': 'TOOL_EXECUTED', 'denied': 'TOOL_DENIED'} \
                    .get(status, 'TOOL_ERROR')
                decision = {'ok': 'allow', 'denied': 'deny'} \
                    .get(status, 'error')
                env['edicai.ai.audit.event'].sudo().create({
                    'name': 'AI tool: %s [%s]' % (tool_name, status),
                    'event_type': event_type,
                    'decision': decision,
                    'reason_code': str(status or '')[:64],
                    'tool_name': tool_name,
                    'user_id': user.id,
                    'company_id': env.company.id,
                    'detail': str(detail or '')[:400],
                    'metadata_json': {'params': _redact_params(params)},
                })
                return
            except Exception:
                _logger.exception(
                    'AI tool audit: durable edicai.ai.audit.event write '
                    'failed; using legacy fallback.')
        summary = 'tool=%s user=%s company=%s status=%s params=%s %s' % (
            tool_name, getattr(user, 'login', user.id),
            company_id, status, _redact_params(params), detail or '')
        summary = summary[:2000]
        for model_name in AUDIT_LOG_MODELS:
            if model_name not in env:
                continue
            Model = env[model_name]
            try:
                fields = Model._fields
                vals = {}
                for fname, fvalue in (
                    ('name', 'AI tool: %s [%s]' % (tool_name, status)),
                    ('tool_name', tool_name),
                    ('user_id', user.id),
                    ('company_id', company_id),
                    ('params', str(_redact_params(params))[:2000]),
                    ('arguments', str(_redact_params(params))[:2000]),
                    ('status', status),
                    ('state', status),
                    ('result', str(detail)[:2000]),
                    ('detail', str(detail)[:2000]),
                ):
                    if fname in fields:
                        vals[fname] = fvalue
                if vals:
                    Model.sudo().create(vals)
                    return
            except Exception:
                _logger.exception(
                    'AI tool audit: failed on model %s; trying next.',
                    model_name)
        # Fallback: ir.logging always exists.
        env['ir.logging'].sudo().create({
            'name': 'edicai.ai.tool.registry',
            'type': 'server',
            'level': 'INFO',
            'message': summary,
            'path': 'edicai_ai.models.ai_tool_registry',
            'func': 'execute_tool',
            'line': 0,
        })
    except Exception:
        _logger.exception('AI tool audit: audit write failed (ignored).')


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def execute_tool(name, params, env, user=None):
    """Allow-listed, scoped, audited dispatch to a registered tool.

    :param name: registered tool/role name.  Unknown names are rejected.
    :param params: dict of caller params; ``company_id`` is **forced** to
        the requester's company (``env.company``).
    :param env: Odoo environment of the requester.
    :param user: ``res.users`` record; defaults to ``env.user``.
    """
    params = dict(params or {})
    user = user or env.user
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        _write_audit(env, name, user, params, 'denied',
                     'unknown tool (not in allow-list)')
        raise UserError(_('Unknown AI tool "%s".') % name)

    # Group gate (XML ids like 'edicai_ai.group_edicai_ai_user', or int ids).
    for group_ref in spec.get('allowed_groups') or []:
        try:
            allowed = (user.has_group(group_ref)
                       if isinstance(group_ref, str)
                       else group_ref in user.groups_id.ids)
        except Exception:
            allowed = False
        if not allowed:
            _write_audit(env, name, user, params, 'denied',
                         'group gate: %s' % group_ref)
            raise UserError(_('You are not allowed to use AI tool "%s".')
                            % name)

    _check_rate_limit(env, name, user, spec)

    # Scope injection: requester company wins, always.
    requester_company = env.company.id
    if params.get('company_id') not in (None, False, requester_company):
        _logger.warning(
            'AI tool "%s": caller company_id=%s overwritten with '
            'requester company_id=%s.', name, params.get('company_id'),
            requester_company)
    params['company_id'] = requester_company

    # Copilot roles resolve to their tool list; they execute nothing.
    if spec.get('kind') == 'role':
        result = {
            'role': name,
            'description': spec.get('description', ''),
            'allowed_tools': list(spec.get('allowed_tools') or []),
            'note': 'Role only lists tools by name; dispatch each '
                    'via execute_tool().',
        }
        _write_audit(env, name, user, params, 'ok',
                     'role resolved: %s' % result['allowed_tools'])
        return result

    # Merge preset params from registration (explicit caller params win,
    # except company_id which was already forced above).
    for key, value in (spec.get('default_params') or {}).items():
        params.setdefault(key, value)
    if spec.get('default_intent'):
        params.setdefault('intent', spec['default_intent'])

    model_name = spec['model']
    method_name = spec['method']
    if model_name not in env:
        _write_audit(env, name, user, params, 'error',
                     'model not installed: %s' % model_name)
        raise UserError(_('AI tool "%s" is unavailable '
                          '(model %s not installed).')
                        % (name, model_name))
    handler = getattr(env[model_name], method_name, None)
    if handler is None:
        _write_audit(env, name, user, params, 'error',
                     'missing method %s.%s' % (model_name, method_name))
        raise UserError(_('AI tool "%s" is misconfigured.') % name)

    try:
        result = handler(dict(params))
    except UserError:
        _write_audit(env, name, user, params, 'error', 'UserError raised')
        raise
    except Exception as exc:
        _logger.exception('AI tool "%s" failed.', name)
        _write_audit(env, name, user, params, 'error', repr(exc)[:500])
        raise UserError(_('AI tool "%s" failed.') % name) from exc

    if isinstance(result, dict):
        keys = sorted(str(k) for k in result.keys())
        rows = result.get('count', result.get('row_count', '?'))
        _write_audit(env, name, user, params, 'ok',
                     'keys=%s rows=%s' % (keys, rows))
    else:
        _write_audit(env, name, user, params, 'ok', type(result).__name__)
    return result


class EdicaiAIToolRegistry(models.AbstractModel):
    """Odoo entry-point for the central AI tool registry."""

    _name = 'edicai.ai.tool.registry'
    _description = 'Central AI Tool Registry'

    @api.model
    def register_tool(self, spec):
        """Register one tool/role spec (also called from XML data files)."""
        return register_tool(spec)

    @api.model
    def execute_tool(self, name, params=None):
        """Execute a registered tool as the current user/company."""
        return execute_tool(name, params or {}, self.env, self.env.user)

    @api.model
    def list_tools(self):
        """Return allow-list metadata (no handlers/payloads)."""
        out = []
        for name in sorted(TOOL_REGISTRY):
            spec = TOOL_REGISTRY[name]
            out.append({
                'name': name,
                'kind': spec.get('kind', 'tool'),
                'description': spec.get('description', ''),
                'model': spec.get('model', ''),
                'method': spec.get('method', ''),
                'allowed_tools': list(spec.get('allowed_tools') or []),
            })
        return out
