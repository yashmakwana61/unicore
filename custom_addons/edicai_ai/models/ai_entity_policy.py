r"""AI Entity Policy — the declarative allow-list of the generic tool
layer (Phase G1, read floor).

WHY THIS EXISTS
---------------
Until Phase 13 every new question type needed ANOTHER hardcoded tool
(per-student fees, cohort fees, per-student attendance, cohort
attendance...).  The generic layer replaces that growth with a small,
fixed set of capability tools (``entity.search``, ``entity.read``,
``entity.aggregate``...) parameterized by THIS table:

* which business models the AI may touch (closed allow-list);
* which operations a caller's groups unlock (deny-by-default);
* which fields are hidden, PII-masked or write-blocked;
* the row caps (exfiltration limit).

Every guarantee of the static tools survives:

* NO SUDO anywhere — a policy row can never grant more than the
  caller's own record rules already allow;
* the model allow-list is structurally closed: only ``edicai.*``
  business models may be registered; ``ir.*``, ``res.*`` and the
  AI's own models (``edicai.ai.*``) are rejected by constraint;
* deny-by-default: an operation is allowed only if the policy row lists
  a group the caller actually holds — an empty group column grants
  NOTHING;
* PII fields are masked in every tool reply and never appear as raw
  values in tool payloads.

This table contains no secrets — every user may READ it (the tools must
consult it as the calling user, without sudo); only the Edicai AI
manager group may create or edit rows.
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

#: Operations of the generic layer. G1 registers the READ floor only;
#: create/update arrive in G2, execute in G3.
OP_VALUES = (
    'search', 'read', 'aggregate', 'describe', 'list',
    'create', 'update', 'delete', 'execute',
)

#: Structurally forbidden model families for entity policies: the ORM
#: itself, contact/settings models, and this module's own models (which
#: would create self-referential data exfiltration paths).
_FORBIDDEN_PREFIXES = ('ir.', 'res.', 'base.', 'mail.', 'edicai.ai.')


def is_allowed_entity_model(model_name):
    """Structural allow-list check (prefix rules only)."""
    name = str(model_name or '').strip()
    return (
        name.startswith('edicai.')
        and not name.startswith(_FORBIDDEN_PREFIXES)
    )


class EdicaiAIEntityPolicy(models.Model):
    """Declarative per-entity grants for the generic AI tools."""

    _name = 'edicai.ai.entity.policy'
    _description = 'AI Entity Policy (generic allow-list)'
    _order = 'model_ref'

    model_ref = fields.Char(
        string='Model', required=True, readonly=True,
        help='Technical model name, e.g. edicai.student. Immutable after '
             'creation because tool grants key on it.')
    label = fields.Char(string='Label', required=True,
                        help='Human label the resolver matches on.')
    synonyms = fields.Char(
        string='Synonyms',
        help='Comma-separated label aliases, e.g. "pupils, learners".')
    read_groups = fields.Char(
        string='Read groups',
        help='Comma-separated group xml ids (edicai_ai.group_...) that '
             'unlock search/read/aggregate/describe. EMPTY = nobody.')
    write_groups = fields.Char(
        string='Write groups',
        help='Comma-separated group xml ids that will unlock '
             'create/update in Phase G2. EMPTY = nobody (read-only now).')
    execute_groups = fields.Char(
        string='Execute groups',
        help='Comma-separated group xml ids that unlock the declared '
             'record ACTIONS (Phase G3, edicai.ai.entity.action). EMPTY = '
             'nobody: no record action runs, whatever the action rows '
             'say. The action row then adds its own allowed_groups.')
    delete_groups = fields.Char(
        string='Delete groups',
        help='Comma-separated group xml ids. Phase G3+ and ALWAYS empty '
             'by default — deletion is disabled for every entity.')
    field_allow = fields.Char(
        string='Field allow-list',
        help='Comma-separated field names; EMPTY = all simple fields '
             'of the model (binary and related fields stay excluded).')
    field_block = fields.Char(
        string='Field block-list',
        help='Comma-separated field names that are never readable or '
             'writable through the AI layer.')
    pii_fields = fields.Char(
        string='PII fields',
        help='Comma-separated fields masked in every reply (kept as '
             '"***" + last 2 characters).')
    ops = fields.Char(
        string='Allowed operations',
        help='Comma-separated from: search, read, aggregate, describe, '
             'list, create, update, delete, execute. Unknown ops are '
             'rejected; empty = describe/list only.')
    max_rows = fields.Integer(
        string='Row cap', default=100,
        help='Hard cap on rows returned by search/read/aggregate for '
             'this entity (search asks for at most this many rows).')
    enabled = fields.Boolean(
        string='Enabled', default=True,
        help='Disabled entities are invisible to EVERY generic tool.')

    _model_ref_uniq = models.Constraint(
        'unique(model_ref)',
        'One entity policy per model (edicai.ai.entity.policy).')

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _csv(self, column):
        """Parse a comma-separated column into lowercase tokens."""
        raw = self[column] or ''
        return tuple(
            token.strip() for token in raw.split(',')
            if token.strip()
        )

    def _ops_list(self):
        return self._csv('ops')

    @api.constrains('model_ref')
    def _check_model_ref(self):
        """Structural allow-list (prefix rules) at write time.

        Model EXISTENCE is deliberately not checked here: this module
        does not depend on the optional edicai_* ERP modules, so seed
        data can (and should) pre-register entities for business
        models that this deployment may install.  An unknown or
        uninstalled model is refused at USE time by the generic tools
        (``edicai.ai.entity.tools._require`` never guesses).
        """
        for policy in self:
            name = policy.model_ref or ''
            if not is_allowed_entity_model(name):
                raise ValidationError(_(
                    'AI Entity Policy: "%s" is outside the allowed '
                    'model families. Only edicai.* business models may '
                    'be registered.') % (name or ''))

    @api.constrains('ops')
    def _check_ops(self):
        for policy in self:
            for op in policy._ops_list():
                if op not in OP_VALUES:
                    raise ValidationError(_(
                        'AI Entity Policy: unknown operation "%s" '
                        '(model %s).') % (op, policy.model_ref))

    @api.constrains('max_rows')
    def _check_max_rows(self):
        for policy in self:
            if not 1 <= (policy.max_rows or 0) <= 500:
                raise ValidationError(_(
                    'AI Entity Policy: row cap must be between 1 and '
                    '500 (model %s).') % policy.model_ref)

    # ------------------------------------------------------------------
    # Introspection helpers (used by the generic tools, no sudo)
    # ------------------------------------------------------------------

    @api.model
    def policy_for(self, model_ref, op):
        """Return the enabled policy row for (model, op) or None.

        Deny-by-default: missing row, disabled entity or an op outside
        the row's ops list all return False. Group checks are done by
        the caller (they need the user record).
        """
        if not is_allowed_entity_model(model_ref):
            return self.env['edicai.ai.entity.policy'].browse()
        policy = self.env['edicai.ai.entity.policy'].search([
            ('model_ref', '=', model_ref),
            ('enabled', '=', True),
        ], limit=1)
        if policy and op not in policy._ops_list():
            return self.env['edicai.ai.entity.policy'].browse()
        return policy

    def caller_has_group(self, column, user):
        """True when ``user`` holds ANY group of the csv column.

        An EMPTY column grants NOTHING (deny-by-default).
        """
        groups = self._csv(column)
        if not groups:
            return False
        for group in groups:
            try:
                if user.has_group(group):
                    return True
            except Exception:
                continue
        return False


class EdicaiAIEntityAction(models.Model):
    """DATA gate of the AI-executable record actions (Phase G3).

    A row here only says "this ERP method MAY be exposed"; it never
    makes a method callable by itself. Execution additionally requires
    the CODE registry (``ai_entity_actions.ENTITY_ACTIONS``), the
    entity policy ``execute`` op + ``execute_groups``, and — like every
    other AI tool — the confirm flow. Deleting every row, or adding a
    row for ``write``/``unlink``/``sudo``, changes nothing on its own.
    """

    _name = 'edicai.ai.entity.action'
    _description = 'AI Entity Action (whitelist for G3 execute)'
    _order = 'model_ref, action'

    model_ref = fields.Char(string='Model', required=True)
    action = fields.Char(
        string='Method', required=True,
        help='State-machine method name, e.g. "action_confirm". ONLY '
             'methods registered here become callable; everything else '
             'stays invisible to the AI layer.')
    label = fields.Char(string='Label')
    allowed_groups = fields.Char(string='Allowed groups')
    needs_approval = fields.Boolean(
        string='Needs approval', default=True)
    enabled = fields.Boolean(string='Enabled', default=True)

    _model_action_uniq = models.Constraint(
        'unique(model_ref, action)',
        'One action whitelist row per model+method '
        '(edicai.ai.entity.action).')

    @api.constrains('model_ref', 'action')
    def _check_action(self):
        for row in self:
            if not is_allowed_entity_model(row.model_ref):
                raise ValidationError(_(
                    'AI Entity Action: "%s" is outside the allowed '
                    'model families.') % row.model_ref)
            # Model EXISTENCE is enforced at USE time (the action may
            # be seeded for an optional ERP module that this deployment
            # installs later), exactly like the entity policy table.
            method = (row.action or '').strip()
            if not method.replace('_', '').isalnum():
                raise ValidationError(_(
                    'AI Entity Action: method "%s" is not a valid '
                    'Python method name.') % row.action)
