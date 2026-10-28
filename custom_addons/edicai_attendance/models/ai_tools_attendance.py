"""
Attendance Nudger Copilot — read-only + draft AI tool layer.

Exposes a small, tool-constrained surface for the attendance-nudger
assistant:

* Read-only tools: ``shortage_list``, ``session_status``.
* One draft tool: ``nudge_draft`` — builds a notification payload via the
  notify-engine DRY-RUN preview path (``_get_template`` +
  ``render_template``) and returns it for HUMAN approval. It never sends
  anything.

Safety properties (mirror the underlying models):

* Session state machine (``edicai.attendance.session``):
  ``scheduled`` -> ``open`` (``action_open_for_marking`` creates one
  ``absent`` record per registered enrollment) -> ``closed``
  (``action_close_session`` locks records + recomputes cumulative stats +
  fires ``maybe_notify_attendance_shortage``). ``action_reopen_session``
  is manager/admin only. These tools NEVER call ``action_open_*``,
  ``action_close_*``, ``action_reopen_*``, ``action_cancel_*`` or
  ``action_face_checkin``.
* Record lock (``edicai.attendance.record.write``): closed-session records
  reject writes without ``force_write_closed_session`` context. These
  tools never call ``create`` / ``write`` / ``unlink`` on any record, so
  they can never trip or bypass the lock.
* Face check-in (``action_face_check_in``) marks ``present`` with
  confidence metadata — reported read-only here via the
  ``face_check_in`` flag; never invoked.
* Cumulative stats: ``present + late`` count as attended over closed,
  non-cancelled, non-holiday sessions; ``shortage_alert`` fires below
  ``min_attendance_percentage``, ``warning_alert`` below
  ``warning_threshold_percentage`` (see ``edicai.attendance.policy``).
* Sending stays with the existing automation
  (``action_close_session`` -> ``maybe_notify_attendance_shortage`` +
  ``send_attendance_shortage_alerts`` cron) and humans. ``nudge_draft``
  NEVER calls ``Engine._safe_emit``, ``send_to_student`` or
  ``send_to_guardian``.

Access control: NO ``sudo()`` anywhere in this file. Every ORM call runs
as the current user so the existing record rules apply
(``security/edicai_attendance_record_rules.xml``: company isolation,
student-own-records, faculty-own-sessions, admin bypass). Company scope
is additionally enforced in every domain via ``env.company``.

Wiring (manual step — existing files are intentionally untouched):

* import this module from ``edicai_attendance/models/__init__.py``;
* add ``data/ai_copilot_prompts.xml`` to the manifest ``data`` list.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# System-prompt storage key (seeded by data/ai_copilot_prompts.xml).
NUDGER_PROMPT_PARAM = 'edicai_attendance.attendance_nudger_system_prompt'

DEFAULT_SYSTEM_PROMPT = (
    'You are the Attendance Nudger, an encouraging assistant for student '
    'attendance. Help users find shortage cases, check session marking '
    'status, and draft supportive nudges. Always cite the attendance '
    'percentage. Never shame. Route disputes to faculty.'
)

# Tool registry — maps tool name to spec for the AI orchestrator.
# Follows the edicai_studio ``TOOL_SPECS`` convention.
TOOL_SPECS = {
    'shortage_list': {
        'desc': (
            'Read-only: students below the policy minimum attendance for '
            'a course offering (company-scoped, uses shortage_alert / '
            'warning_alert computed against edicai.attendance.policy).'
        ),
        'args': ['offering_id', 'include_warning', 'limit'],
        'params': {
            'offering_id': (
                'Optional course offering id. When omitted, lists '
                'shortages across all visible offerings.'
            ),
            'include_warning': (
                'Also include students in the warning band (below warning '
                'threshold but above minimum). Default False.'
            ),
            'limit': 'Max students returned (default 50, max 100).',
        },
        'readonly': True,
    },
    'session_status': {
        'desc': (
            'Read-only: attendance sessions needing marking (scheduled / '
            'open), or closed sessions for context. Company-scoped. '
            'Never opens, closes, or reopens anything.'
        ),
        'args': ['offering_id', 'session_state', 'limit'],
        'params': {
            'offering_id': 'Optional course offering id to filter by.',
            'session_state': (
                'Optional state filter: scheduled, open, closed, '
                'cancelled. Default lists scheduled + open (needing '
                'marking).'
            ),
            'limit': 'Max sessions returned (default 50, max 100).',
        },
        'readonly': True,
    },
    'nudge_draft': {
        'desc': (
            'DRAFT ONLY: build an attendance-nudge notification payload '
            'for one student + offering via the notify-engine DRY-RUN '
            'preview (template render only). Returns the payload for '
            'human approval; never sends anything.'
        ),
        'args': ['student_id', 'offering_id', 'channel'],
        'params': {
            'student_id': 'Database id of the edicai.student record.',
            'offering_id': 'Database id of the edicai.course.offering.',
            'channel': (
                'Preview channel: email, whatsapp, inapp, or all '
                '(default all).'
            ),
        },
        'readonly': True,
        'draft': True,
    },
}

_SHORTAGE_TRIGGER = 'attendance_shortage'
_WARNING_TRIGGER = 'attendance_warning'
_PREVIEW_CHANNELS = ('email', 'whatsapp', 'inapp')


class AttendanceAICopilot(models.AbstractModel):
    """Attendance Nudger Copilot — read-only + draft helpers."""

    _name = 'attendance.ai.copilot'
    _description = 'Attendance Nudger Copilot (read-only AI tools)'

    # ------------------------------------------------------------------
    # Registry / chat entry
    # ------------------------------------------------------------------

    @api.model
    def get_tool_specs(self):
        """Return the TOOL_SPECS registry for the AI orchestrator."""
        return TOOL_SPECS

    @api.model
    def _get_system_prompt(self):
        prompt = self.env['ir.config_parameter'].sudo().get_param(
            NUDGER_PROMPT_PARAM, default='',
        )
        return prompt or DEFAULT_SYSTEM_PROMPT

    @api.model
    def chat(self, prompt):
        """One-shot question answering with the nudger system prompt.

        Tool execution itself is driven by the caller using
        ``get_tool_specs``; this helper only grounds plain questions.
        """
        if not prompt:
            raise UserError(_('Please provide a question for the nudger.'))
        provider = self.env['edicai.ai.provider']
        return provider.generate_text(
            prompt, system_prompt=self._get_system_prompt(),
        )

    @api.model
    def check_tool_access(self, tool_name):
        """Allow-list gate: only TOOL_SPECS names may run."""
        if tool_name not in TOOL_SPECS:
            raise UserError(_('Unknown copilot tool: %s.') % tool_name)
        return True

    @api.model
    def run_tool(self, name, **kwargs):
        """Dispatch ONLY to tools declared in TOOL_SPECS."""
        self.check_tool_access(name)
        handler = getattr(self, '_tool_%s' % name, None)
        if handler is None:
            raise UserError(_('Copilot tool not implemented: %s.') % name)
        return handler(**kwargs)

    # ------------------------------------------------------------------
    # Shared helpers (read-only, no sudo — record rules apply)
    # ------------------------------------------------------------------

    @api.model
    def _company_id(self):
        return self.env.company.id

    @api.model
    def _cite(self, records):
        """Build cite-oriented sources for a recordset."""
        sources = []
        for rec in records:
            try:
                label = rec.display_name
            except Exception:
                label = rec._name
            sources.append({
                'model': rec._name,
                'id': rec.id,
                'display_name': label,
            })
        return sources

    # ------------------------------------------------------------------
    # Tool: shortage_list
    # ------------------------------------------------------------------

    @api.model
    def _tool_shortage_list(self, offering_id=None, include_warning=False,
                            limit=50, threshold=None):
        """Students below the policy minimum per offering.

        Reads ``edicai.attendance.record`` rows flagged by the stored
        ``shortage_alert`` / ``warning_alert`` computes (which already
        apply ``edicai.attendance.policy.get_policy_for_offering``), then
        de-duplicates to one row per student + offering like the
        ``send_attendance_shortage_alerts`` cron does. No writes, no
        ``action_*`` calls.
        """
        try:
            limit = int(limit or 50)
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 100))
        if threshold is not None:
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                raise UserError(_('Invalid attendance threshold.'))
            if not 0 < threshold <= 80:
                raise UserError(_('Unsupported attendance threshold.'))
        company_id = self._company_id()

        domain = [('company_id', '=', company_id)]
        if offering_id:
            domain.append(
                ('course_offering_id', '=', int(offering_id)))
        if include_warning:
            domain.append('|')
        domain += [('shortage_alert', '=', True)]
        if include_warning:
            domain.append(('warning_alert', '=', True))

        # Record rules apply (no sudo): students see only their own rows,
        # faculty only their own sessions' rows.
        records = self.env['edicai.attendance.record'].search(
            domain, order='id desc')
        records.check_access('read')

        Policy = self.env['edicai.attendance.policy']
        seen = set()
        student_ids = set()
        rows = []
        sources = []
        total_pairs = 0
        for rec in records:
            pair = (
                rec.student_id.id,
                rec.course_offering_id.id
                if rec.course_offering_id else 0,
            )
            if pair in seen:
                continue
            seen.add(pair)
            pct = rec.cumulative_attendance_percentage or 0.0
            if threshold is not None and pct >= threshold:
                continue
            total_pairs += 1
            student_ids.add(rec.student_id.id)
            policy = Policy.get_policy_for_offering(
                rec.course_offering_id) if rec.course_offering_id else False
            minimum = (
                policy.min_attendance_percentage if policy else 75.0)
            warning = (
                policy.warning_threshold_percentage if policy else 80.0)
            row = {
                'student_id': rec.student_id.id,
                'student_name': rec.student_id.display_name,
                'offering_id': (
                    rec.course_offering_id.id
                    if rec.course_offering_id else False),
                'offering_name': (
                    rec.course_offering_id.display_name
                    if rec.course_offering_id else False),
                'course_name': (
                    rec.course_id.display_name
                    if rec.course_id else False),
                'cumulative_attendance_percentage': round(pct, 2),
                'total_sessions_held': rec.total_sessions_held,
                'sessions_present': rec.sessions_present,
                'sessions_late': rec.sessions_late,
                'sessions_absent': rec.sessions_absent,
                'sessions_excused': rec.sessions_excused,
                'face_check_in': rec.face_check_in,
                'shortage_alert': rec.shortage_alert,
                'warning_alert': rec.warning_alert,
                'min_required': minimum,
                'warning_threshold': warning,
                'gap_points': round(minimum - pct, 2),
                'exam_eligibility_linked': (
                    bool(policy.is_exam_eligibility_linked)
                    if policy else True),
            }
            if len(rows) < limit:
                rows.append(row)
                sources += self._cite(rec.student_id)
            # Else keep scanning for exact totals without retaining more
            # candidate payloads than the declared bound.

        rows.sort(
            key=lambda r: r['cumulative_attendance_percentage'])
        return {
            'company_id': company_id,
            'offering_id': int(offering_id) if offering_id else False,
            'include_warning': bool(include_warning),
            'count': len(rows),
            'total_count': total_pairs,
            'students_count': len(student_ids),
            'truncated': total_pairs > len(rows),
            'shortages': rows,
            'sources': sources[:limit],
        }

    @api.model
    def shortage_summary(self, include_warning=True, limit=10,
                         threshold=None):
        """Institution-wide attendance-shortage AGGREGATE.

        Answers the cohort question: *how many students are below the
        attendance policy right now?* — a count plus the worst cases.

        Scope: the active company, with the caller's record rules
        applied (no ``sudo``): a portal student only ever sees their own
        row, a faculty member only their own sessions' rows.

        Read-only: no record is written.
        """
        try:
            limit = max(1, min(int(limit or 10), 50))
        except (TypeError, ValueError):
            limit = 10
        result = self._tool_shortage_list(
            offering_id=None,
            include_warning=include_warning or threshold is not None,
            limit=100,
            threshold=threshold,
        )
        rows = result.get('shortages') or []
        per_student = {}
        for row in rows:
            sid = row.get('student_id')
            pct = row.get('cumulative_attendance_percentage') or 0.0
            current = per_student.get(sid)
            if current is None or pct < current['percentage']:
                per_student[sid] = {
                    'student_id': sid,
                    'student': row.get('student_name'),
                    'percentage': pct,
                    'offering': row.get('offering_name'),
                    'min_required': row.get('min_required'),
                    'gap_points': row.get('gap_points'),
                }
        worst = sorted(
            per_student.values(),
            key=lambda r: (r['percentage'] if r['percentage'] is not None
                            else 0),
        )
        return {
            'scope': 'company',
            'students_short': result.get('students_count') or len(per_student),
            'shortage_rows': result.get('total_count') or len(rows),
            'truncated': bool(result.get('truncated')),
            'include_warning': bool(include_warning),
            'threshold': threshold,
            'worst_students': worst[:limit],
            'sources': (result.get('sources') or [])[:limit],
        }

    # ------------------------------------------------------------------
    # Tool: session_status
    # ------------------------------------------------------------------

    @api.model
    def _tool_session_status(self, offering_id=None, session_state=None,
                             limit=50):
        """Open/closed sessions needing marking (read-only).

        Defaults to ``scheduled`` + ``open`` sessions (the ones needing
        action). Never calls ``action_open_for_marking``,
        ``action_close_session``, ``action_reopen_session``,
        ``action_cancel_session`` or ``action_face_checkin``.
        """
        try:
            limit = int(limit or 50)
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 100))
        company_id = self._company_id()

        domain = [('company_id', '=', company_id)]
        if offering_id:
            domain.append(
                ('course_offering_id', '=', int(offering_id)))
        if session_state:
            if session_state not in (
                    'scheduled', 'open', 'closed', 'cancelled'):
                raise UserError(
                    _('Invalid session_state: %s.') % session_state)
            domain.append(('session_state', '=', session_state))
        else:
            domain.append(
                ('session_state', 'in', ['scheduled', 'open']))

        sessions = self.env['edicai.attendance.session'].search(
            domain, order='session_date asc', limit=limit,
        )
        sessions.check_access('read')

        rows = []
        for sess in sessions:
            state = sess.session_state
            if state == 'scheduled':
                next_action = _(
                    'Open for marking (faculty action in the UI).')
            elif state == 'open':
                next_action = _(
                    'Mark attendance, then close (faculty action in UI).')
            elif state == 'closed':
                next_action = _('Locked; reopening needs manager/admin.')
            else:
                next_action = _('Cancelled; no marking required.')
            rows.append({
                'session_id': sess.id,
                'display_name': sess.display_name,
                'session_date': (
                    str(sess.session_date)
                    if sess.session_date else False),
                'session_state': state,
                'needs_marking': state in ('scheduled', 'open'),
                'next_action': next_action,
                'offering_id': (
                    sess.course_offering_id.id
                    if sess.course_offering_id else False),
                'offering_name': (
                    sess.course_offering_id.display_name
                    if sess.course_offering_id else False),
                'course_name': (
                    sess.course_id.display_name
                    if sess.course_id else False),
                'instructor_name': (
                    sess.instructor_id.display_name
                    if sess.instructor_id else False),
                'total_students': sess.total_students,
                'present_count': sess.present_count,
                'absent_count': sess.absent_count,
                'late_count': sess.late_count,
                'excused_count': sess.excused_count,
                'attendance_percentage': sess.attendance_percentage,
                'is_holiday': sess.is_holiday,
                'is_cancelled': sess.is_cancelled,
            })
        return {
            'company_id': company_id,
            'offering_id': int(offering_id) if offering_id else False,
            'session_state': session_state or 'scheduled,open',
            'count': len(rows),
            'sessions': rows,
            'sources': self._cite(sessions),
            'guards': _(
                'This tool never opens, closes, reopens, cancels, or '
                'face-checks-in sessions. Marking stays a human faculty '
                'action in the UI.',
            ),
        }

    # ------------------------------------------------------------------
    # Tool: nudge_draft (DRY-RUN preview — never sends)
    # ------------------------------------------------------------------

    @api.model
    def _tool_nudge_draft(self, student_id, offering_id, channel='all'):
        """Build a nudge payload for human approval (no side effects).

        Mirrors the variable set used by
        ``edicai.notification.engine.maybe_notify_attendance_shortage``
        (``student_name`` / ``attendance`` / ``course_name`` /
        ``minimum_required``) and renders the matching
        ``attendance_shortage`` / ``attendance_warning`` templates via
        ``Engine._get_template`` + ``template.render_template`` — the
        read-only preview half of the notify engine. NEVER calls
        ``_safe_emit``, ``send_to_student`` or ``send_to_guardian``;
        sending stays with the existing shortage automation + humans.
        """
        if not student_id or not offering_id:
            raise UserError(_(
                'student_id and offering_id are both required.'))
        channel = (channel or 'all').strip().lower()
        if channel not in ('email', 'whatsapp', 'inapp', 'all'):
            raise UserError(_('Invalid channel: %s.') % channel)
        wanted = (
            list(_PREVIEW_CHANNELS) if channel == 'all' else [channel])
        company_id = self._company_id()

        student = self.env['edicai.student'].browse(int(student_id))
        if not student.exists():
            raise UserError(_('Student #%s not found.') % student_id)
        student.display_name  # noqa: B018 - access check under rules
        offering = self.env['edicai.course.offering'].browse(
            int(offering_id))
        if not offering.exists():
            raise UserError(
                _('Course offering #%s not found.') % offering_id)
        offering.display_name  # noqa: B018 - access check under rules
        if student.company_id.id != company_id:
            raise UserError(_(
                'Student belongs to another institution.'))
        if offering.company_id.id != company_id:
            raise UserError(_(
                'Course offering belongs to another institution.'))

        latest = self.env['edicai.attendance.record'].search([
            ('company_id', '=', company_id),
            ('student_id', '=', student.id),
            ('course_offering_id', '=', offering.id),
        ], order='session_date desc', limit=1)
        if latest:
            pct = latest.cumulative_attendance_percentage or 0.0
            counts = {
                'total_sessions_held': latest.total_sessions_held,
                'sessions_present': latest.sessions_present,
                'sessions_late': latest.sessions_late,
                'sessions_absent': latest.sessions_absent,
                'sessions_excused': latest.sessions_excused,
                'face_check_in': latest.face_check_in,
                'shortage_alert': latest.shortage_alert,
                'warning_alert': latest.warning_alert,
            }
        else:
            pct = 0.0
            counts = {
                'total_sessions_held': 0,
                'sessions_present': 0,
                'sessions_late': 0,
                'sessions_absent': 0,
                'sessions_excused': 0,
                'face_check_in': False,
                'shortage_alert': False,
                'warning_alert': False,
                'note': _(
                    'No attendance records yet for this student + '
                    'offering; percentage shown as 0.0.'),
            }

        policy = self.env[
            'edicai.attendance.policy'].get_policy_for_offering(offering)
        minimum = str(
            policy.min_attendance_percentage if policy else '75')
        trigger_event = (
            _SHORTAGE_TRIGGER
            if pct < float(minimum) else _WARNING_TRIGGER)

        variables = {
            'student_name': student.display_name,
            'attendance': str(round(pct, 1)),
            'course_name': (
                offering.course_id.display_name
                if offering.course_id else offering.display_name),
            'minimum_required': minimum,
        }

        previews = {}
        if 'edicai.notification.engine' in self.env:
            Engine = self.env['edicai.notification.engine']
            for ch in wanted:
                try:
                    template = Engine._get_template(
                        trigger_event, ch, company_id)
                except Exception as exc:
                    _logger.warning(
                        'Nudge draft preview lookup failed (%s/%s): %s',
                        trigger_event, ch, exc)
                    previews[ch] = {'missing': True, 'error': str(exc)}
                    continue
                if not template:
                    previews[ch] = {
                        'missing': True,
                        'note': _(
                            'No %s template for %s in this institution.')
                        % (ch, trigger_event),
                    }
                    continue
                try:
                    rendered = template.render_template(dict(variables))
                except Exception as exc:
                    _logger.warning(
                        'Nudge draft render failed (%s/%s): %s',
                        trigger_event, ch, exc)
                    previews[ch] = {'missing': True, 'error': str(exc)}
                    continue
                previews[ch] = {
                    'missing': False,
                    'template_id': template.id,
                    'template_name': template.display_name,
                    'rendered': rendered,
                }
        else:
            for ch in wanted:
                previews[ch] = {
                    'missing': True,
                    'note': _(
                        'edicai.notification.engine is not installed; '
                        'variables shown without template render.'),
                }

        _logger.info(
            'Attendance Nudger DRY-RUN for student %s / offering %s '
            '(nothing sent).', student.id, offering.id,
        )
        return {
            'type': 'nudge_draft',
            'trigger_event': trigger_event,
            'student_id': student.id,
            'student_name': student.display_name,
            'offering_id': offering.id,
            'offering_name': offering.display_name,
            'cumulative_attendance_percentage': round(pct, 2),
            'counts': counts,
            'variables': variables,
            'previews': previews,
            'requires_human_approval': True,
            'sources': (
                self._cite(student) + self._cite(offering)
                + self._cite(latest)),
            'warning': _(
                'DRAFT ONLY — nothing was sent, opened, closed, or '
                'written. Sending stays with the existing shortage '
                'automation and a human approver.',
            ),
        }
