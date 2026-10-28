"""
Grievance Triager Copilot — read-only AI tool layer for edicai_grievance.

Triage suggestions only. These tools NEVER:

* write on any record (no ``category_id`` / ``assigned_team_id`` /
  ``state`` changes — human staff resolve via ``action_resolve`` /
  ``action_cancel`` / ``action_in_progress`` / ``action_escalate``);
* post messages, schedule activities, or send notifications
  (portal + ``_send_notification`` / ``_notify_decision`` stay human-driven);
* print full contacts in reasoning output (PII minimization — see
  ``data/ai_copilot_prompts.xml``).

Model surface mirrored from ``models/edicai_grievance.py``:

* ``edicai.grievance.request`` states:
  new / in_progress / resolved / escalated / cancelled.
* ``edicai.grievance.category`` / ``edicai.grievance.team`` are
  company-scoped (``company_id in [company, False]``) — every read
  applies the same domain.
* ``edicai.mixin`` company scope is honoured by reading as the current
  user (record rules / ACLs apply; access errors propagate).

SLA pattern (comparison only — ``edicai_student_leave`` is NOT edited):

* like ``edicai.student.leave.request._compute_leave_duration``,
  age is derived read-only as ``today - create_date`` (no stored field,
  no write).  There is no per-category SLA field on
  ``edicai.grievance.category``, so targets come from the
  ``edicai_grievance.sla_days_default`` (+ optional per-category
  ``edicai_grievance.sla_days.<category_id>``) config parameters,
  defaulting to 7 days.

Wiring (manual step — existing files are intentionally untouched):

* import this module from ``edicai_grievance/models/__init__.py``::

      from . import ai_tools_grievance

* add ``data/ai_copilot_prompts.xml`` to the manifest ``data`` list.
"""

import logging
import re
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TOOL_SPECS = {
    'category_suggest': {
        'desc': (
            'Read-only: keyword-match a grievance description against '
            'existing company-scoped categories; returns ranked '
            'suggestions with a confidence note. NEVER auto-sets '
            'category_id.'
        ),
        'args': ['grievance_id', 'description'],
        'readonly': True,
    },
    'urgency_score': {
        'desc': (
            'Read-only: heuristic urgency score (0-100) from safety '
            'keywords, grievance age, repeat-complainant count and '
            'escalation state, plus human-readable reasons. '
            'Never changes state.'
        ),
        'args': ['grievance_id'],
        'readonly': True,
    },
    'team_route_suggest': {
        'desc': (
            'Read-only: suggests a resolution team from company-scoped '
            'teams using open-workload reads. NEVER assigns '
            'assigned_team_id.'
        ),
        'args': ['grievance_id'],
        'readonly': True,
    },
    'sla_status': {
        'desc': (
            'Read-only: grievance age (days) vs per-category target; '
            'flags breached/at-risk items. Never resolves or cancels.'
        ),
        'args': ['grievance_id'],
        'readonly': True,
    },
}

# System-prompt storage key (seeded by data/ai_copilot_prompts.xml).
TRIAGER_PROMPT_PARAM = 'edicai_grievance.ai_triager_prompt'

DEFAULT_SLA_DAYS = 7
AT_RISK_DAYS_BEFORE_BREACH = 2

# Safety / urgency keyword sets (lowercase substring match).
_SAFETY_KEYWORDS = (
    'harassment', 'harass', 'assault', 'abuse', 'threat',
    'unsafe', 'safety', 'violence', 'bullying', 'ragging',
    'discrimination', 'suicide', 'self-harm', 'self harm',
)
_URGENT_KEYWORDS = (
    'urgent', 'immediately', 'emergency', 'critical', 'deadline',
    'exam tomorrow', 'suspended', 'rusticat', 'medical', 'hospital',
    'police', 'legal', 'court',
)
# Category keyword hints applied against category names as fallback
# when the description shares no token with any category name.
_CATEGORY_KEYWORDS = {
    'academic': ('exam', 'marks', 'grade', 'result', 'paper', 'faculty',
                 'teacher', 'lecture', 'class', 'syllabus', 'attendance'),
    'hostel': ('hostel', 'room', 'warden', 'mess', 'food', 'accommodation'),
    'fee': ('fee', 'payment', 'dues', 'refund', 'scholarship', 'fine'),
    'transport': ('bus', 'transport', 'cab', 'route', 'driver'),
    'library': ('library', 'book', 'issue', 'return'),
    'harassment': _SAFETY_KEYWORDS,
}


def _tokenize(text):
    """Lowercase word tokens of 3+ chars (PII-free keyword matching)."""
    return set(
        tok for tok in re.findall(r'[a-z]+', (text or '').lower())
        if len(tok) >= 3
    )


def _mask_name(name):
    """First-name + initial only, for PII minimization in outputs."""
    parts = (name or '').split()
    if not parts:
        return _('(unnamed)')
    if len(parts) == 1:
        return parts[0][:1] + '***'
    return '%s %s.' % (parts[0], parts[-1][:1])


class GrievanceAICopilot(models.AbstractModel):
    """Grievance Triager — suggestion-only helpers. No writes."""

    _name = 'grievance.ai.copilot'
    _description = 'Grievance Triager Copilot (read-only AI tools)'

    # ------------------------------------------------------------------
    # Shared helpers (read-only, company scope, no sudo)
    # ------------------------------------------------------------------

    @api.model
    def _scoped_grievance(self, grievance_id):
        """Fetch one grievance readable by the current user."""
        if not grievance_id:
            raise UserError(_('Provide grievance_id.'))
        grievance = self.env['edicai.grievance.request'].browse(
            int(grievance_id),
        )
        if not grievance.exists():
            raise UserError(_('Grievance not found.'))
        grievance.check_access('read')
        return grievance

    @api.model
    def _company_categories(self, company_id):
        """Categories visible to *company_id* (same domain as the form)."""
        return self.env['edicai.grievance.category'].search([
            ('company_id', 'in', [company_id, False]),
        ])

    @api.model
    def _company_teams(self, company_id):
        """Teams visible to *company_id* (same domain as the form)."""
        return self.env['edicai.grievance.team'].search([
            ('company_id', 'in', [company_id, False]),
        ])

    @api.model
    def _grievance_age_days(self, grievance):
        """Read-only age in days (leave-duration compute pattern)."""
        create_date = grievance.create_date
        if not create_date:
            return 0
        return max(0, (fields.Date.today() - create_date.date()).days)

    @api.model
    def _sla_target_days(self, grievance):
        """Per-category SLA target; falls back to the default (7 days)."""
        ICP = self.env['ir.config_parameter']
        default = ICP.get_param(
            'edicai_grievance.sla_days_default',
            default=str(DEFAULT_SLA_DAYS),
        )
        try:
            fallback = int(default)
        except (ValueError, TypeError):
            fallback = DEFAULT_SLA_DAYS
        if grievance.category_id:
            per_cat = ICP.get_param(
                'edicai_grievance.sla_days.%d' % grievance.category_id.id,
                default='',
            )
            try:
                if per_cat not in (False, '', None):
                    return max(1, int(per_cat))
            except (ValueError, TypeError):
                pass
        return max(1, fallback)

    @api.model
    def _repeat_count(self, grievance):
        """Open/history count for the same complainant (read-only)."""
        if not grievance.raised_by_id:
            return 0
        return self.env['edicai.grievance.request'].search_count([
            ('raised_by_id', '=', grievance.raised_by_id.id),
            ('company_id', '=', grievance.company_id.id),
        ])

    # ------------------------------------------------------------------
    # Tool: category_suggest
    # ------------------------------------------------------------------

    @api.model
    def category_suggest(self, grievance_id=None, description=None, limit=3):
        """Rank existing categories by keyword overlap.

        Never writes ``category_id`` — the caller (human) decides.
        """
        limit = max(1, min(int(limit or 3), 10))
        if grievance_id:
            grievance = self._scoped_grievance(grievance_id)
            text = grievance.description or ''
            categories = self._company_categories(
                grievance.company_id.id,
            )
        elif description:
            text = description
            categories = self._company_categories(self.env.company.id)
        else:
            raise UserError(_(
                'Provide grievance_id or description text.',
            ))
        tokens = _tokenize(text)
        scored = []
        for cat in categories:
            name_tokens = _tokenize(cat.name)
            overlap = tokens & name_tokens
            hint_hits = [
                kw for kw in _CATEGORY_KEYWORDS.get(
                    (cat.name or '').strip().lower(), ())
                if kw in (text or '').lower()
            ]
            score = len(overlap) * 2 + len(hint_hits)
            if score:
                scored.append((score, cat))
        scored.sort(key=lambda item: (-item[0], item[1].name or ''))
        total = sum(s for s, _ in scored) or 1
        suggestions = [
            {
                'category_id': cat.id,
                'category_name': cat.name,
                'keyword_hits': sorted(
                    list(_tokenize(text) & _tokenize(cat.name)),
                ),
                'confidence': round(score / total, 2),
            }
            for score, cat in scored[:limit]
        ]
        if suggestions:
            note = _(
                'Top match "%s" covers %d%% of the keyword weight; '
                'a human must confirm before setting the category.',
            ) % (
                suggestions[0]['category_name'],
                int(suggestions[0]['confidence'] * 100),
            )
        else:
            note = _(
                'No category keywords matched; a human must pick '
                'the category manually.',
            )
        return {
            'type': 'category_suggestion',
            'grievance_id': int(grievance_id) if grievance_id else False,
            'suggestions': suggestions,
            'confidence_note': note,
            'auto_set': False,
            'warning': _(
                'SUGGESTION ONLY — category_id was not changed. '
                'A staff member must set it.',
            ),
        }

    # ------------------------------------------------------------------
    # Tool: urgency_score
    # ------------------------------------------------------------------

    @api.model
    def urgency_score(self, grievance_id):
        """Heuristic 0-100 urgency score + reasons. Read-only."""
        grievance = self._scoped_grievance(grievance_id)
        text = (grievance.description or '').lower()
        reasons = []
        score = 0

        safety_hits = [kw for kw in _SAFETY_KEYWORDS if kw in text]
        if safety_hits:
            score += 50
            reasons.append(_(
                'Safety keywords matched: %s.',
            ) % ', '.join(sorted(set(safety_hits))))
        urgent_hits = [kw for kw in _URGENT_KEYWORDS if kw in text]
        if urgent_hits:
            score += 20
            reasons.append(_(
                'Urgency keywords matched: %s.',
            ) % ', '.join(sorted(set(urgent_hits))))

        age = self._grievance_age_days(grievance)
        if age >= self._sla_target_days(grievance):
            score += 15
            reasons.append(_(
                'Open for %d day(s), at or past the SLA target.',
            ) % age)
        elif age >= 3:
            score += 5
            reasons.append(_(
                'Open for %d day(s) without resolution.',
            ) % age)

        repeats = self._repeat_count(grievance)
        if repeats >= 3:
            score += 10
            reasons.append(_(
                'Complainant has raised %d grievance(s) '
                '(possible repeat issue).',
            ) % repeats)

        if grievance.state == 'escalated':
            score += 10
            reasons.append(_('Already escalated — needs senior review.'))
        elif grievance.state in ('resolved', 'cancelled'):
            reasons.append(_(
                'Already %s — no triage action needed; '
                'a human owns the outcome.',
            ) % grievance.state)

        score = max(0, min(100, score))
        if score >= 70:
            band = 'critical'
        elif score >= 40:
            band = 'high'
        elif score >= 15:
            band = 'normal'
        else:
            band = 'low'
        return {
            'type': 'urgency_score',
            'grievance_id': grievance.id,
            'grievance_state': grievance.state,
            'complainant': _mask_name(
                grievance.raised_by_id.display_name
                if grievance.raised_by_id else '',
            ),
            'score': score,
            'band': band,
            'reasons': reasons,
            'age_days': age,
            'repeat_complaints': repeats,
            'warning': _(
                'HEURISTIC ONLY — score does not change state or '
                'priority; a human must triage.',
            ),
        }

    # ------------------------------------------------------------------
    # Tool: team_route_suggest
    # ------------------------------------------------------------------

    @api.model
    def team_route_suggest(self, grievance_id):
        """Suggest a team from open-workload reads. Never assigns."""
        grievance = self._scoped_grievance(grievance_id)
        teams = self._company_teams(grievance.company_id.id)
        if not teams:
            raise UserError(_(
                'No grievance teams are configured for this institution.',
            ))
        Request = self.env['edicai.grievance.request']
        rows = []
        for team in teams:
            open_count = Request.search_count([
                ('assigned_team_id', '=', team.id),
                ('state', 'in', ('new', 'in_progress', 'escalated')),
            ])
            member_count = len(team.member_ids)
            rows.append({
                'team_id': team.id,
                'team_name': team.name,
                'open_grievances': open_count,
                'member_count': member_count,
            })
        rows.sort(key=lambda r: (r['open_grievances'], r['team_name'] or ''))
        suggested = rows[0]
        category_name = (
            grievance.category_id.name if grievance.category_id else False
        )
        return {
            'type': 'team_route_suggestion',
            'grievance_id': grievance.id,
            'grievance_state': grievance.state,
            'category_name': category_name,
            'suggested_team_id': suggested['team_id'],
            'suggested_team_name': suggested['team_name'],
            'workload': rows,
            'rationale': _(
                '"%s" has the lowest open load (%d open, %d member(s)).',
            ) % (
                suggested['team_name'],
                suggested['open_grievances'],
                suggested['member_count'],
            ),
            'assigned': False,
            'warning': _(
                'SUGGESTION ONLY — assigned_team_id was not changed. '
                'A staff member must assign the team.',
            ),
        }

    # ------------------------------------------------------------------
    # Tool: sla_status
    # ------------------------------------------------------------------

    @api.model
    def sla_status(self, grievance_id=None, include_breach_list=True):
        """Age vs per-category target; breach / at-risk flags.

        With a single *grievance_id* returns that record's status;
        always includes the open-item breach list for the company
        (read-only, capped at 50 rows).
        """
        ICP = self.env['ir.config_parameter']
        try:
            at_risk_margin = int(ICP.get_param(
                'edicai_grievance.sla_at_risk_margin',
                default=str(AT_RISK_DAYS_BEFORE_BREACH),
            ))
        except (ValueError, TypeError):
            at_risk_margin = AT_RISK_DAYS_BEFORE_BREACH

        def _status_for(grievance):
            age = self._grievance_age_days(grievance)
            target = self._sla_target_days(grievance)
            remaining = target - age
            if grievance.state in ('resolved', 'cancelled'):
                status = 'closed'
            elif age >= target:
                status = 'breached'
            elif age >= target - at_risk_margin:
                status = 'at_risk'
            else:
                status = 'on_track'
            return {
                'grievance_id': grievance.id,
                'reference': 'GRV-%d' % grievance.id,
                'state': grievance.state,
                'category_name': (
                    grievance.category_id.name
                    if grievance.category_id else False
                ),
                'age_days': age,
                'sla_target_days': target,
                'days_remaining': remaining,
                'status': status,
            }

        current = None
        company_id = self.env.company.id
        if grievance_id:
            grievance = self._scoped_grievance(grievance_id)
            current = _status_for(grievance)
            company_id = grievance.company_id.id

        breach_list = []
        if include_breach_list:
            open_items = self.env['edicai.grievance.request'].search([
                ('company_id', '=', company_id),
                ('state', 'not in', ('resolved', 'cancelled')),
            ], limit=200)
            for item in open_items:
                row = _status_for(item)
                if row['status'] in ('breached', 'at_risk'):
                    breach_list.append(row)
            breach_list.sort(
                key=lambda r: (r['status'] != 'breached', -r['age_days']),
            )
            breach_list = breach_list[:50]

        return {
            'type': 'sla_status',
            'grievance': current,
            'breach_list': breach_list,
            'breached_count': sum(
                (1 for r in breach_list if r['status'] == 'breached'),
            ),
            'at_risk_count': sum(
                (1 for r in breach_list if r['status'] == 'at_risk'),
            ),
            'default_target_days': self._sla_target_days(
                self.env['edicai.grievance.request'],
            ) if not grievance_id else (
                current['sla_target_days'] if current else DEFAULT_SLA_DAYS
            ),
            'warning': _(
                'READ-ONLY — SLA status never resolves, cancels, or '
                'reassigns; a human must act on breaches.',
            ),
        }
