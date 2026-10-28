"""
Grade Copilot — suggest-only AI tool implementations.

Suggest-only surface for faculty assistance. This module NEVER grades:

* Read-only tools: ``anomaly_flags``, ``gradebook_preview``,
  ``publish_readiness``.
* One draft tool: ``rubric_suggest`` — prepares a criterion list for
  HUMAN review. It never creates an ``edicai.assignment.rubric`` record.

Hard safety properties (mirror the underlying models):

* ``edicai.grade.entry`` states:
  draft → submitted → verified → published → locked.
* The state-machine methods ``action_submit``, ``action_verify``,
  ``action_publish``, ``action_lock`` and ``action_reset_draft`` are
  NEVER called from here. ``entry_state`` is only read.
* Maker-checker (``action_verify``: registrar/manager/admin only, and
  the faculty who entered the marks cannot verify their own entry) is
  respected by reporting readiness instead of verifying anything.
* No marks are ever written: ``internal_marks``, ``external_marks``,
  ``letter_grade`` and ``grade_point`` are read-only inputs here.
  ``credits_applied`` / enrollment / CGPA side effects therefore can
  never trigger from these tools.
* Anomaly flags use neutral, non-accusatory language only ("suggested
  for human review"). They never accuse, never judge, never conclude
  misconduct.
* Company scope: every search is restricted to the current company and
  no ``sudo()`` call appears in this file. Access errors propagate so
  record rules keep applying.
* Optional-module safety: ``edicai_grading`` does not depend on
  ``edicai_assignment`` or ``edicai_gradebook``. Every access to those
  models goes through ``self.env.get(...)`` with a graceful fallback
  so this file stays import-safe when they are not installed.
"""

import logging
import math

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TOOL_SPECS = {
    'rubric_suggest': {
        'desc': (
            'DRAFT ONLY: propose a criterion list (names, suggested '
            'points, descriptions) derived from the grade scale and the '
            'assignment type, for human review. Never creates a rubric.'
        ),
        'args': ['scale_id', 'assignment_type', 'max_marks',
                 'assignment_id'],
        'readonly': True,
        'draft': True,
    },
    'anomaly_flags': {
        'desc': (
            'Read-only: statistics (mean/std) for one offering plus '
            'entries beyond the z-score threshold or clustered at the '
            'observed max/min. Neutral reasons only, no judgement.'
        ),
        'args': ['offering_id', 'threshold_std', 'basis'],
        'readonly': True,
    },
    'gradebook_preview': {
        'desc': (
            'Read-only: recompute the gradebook roll-up for one offering '
            'and show the delta versus current internal_marks WITHOUT '
            'writing anything.'
        ),
        'args': ['offering_id'],
        'readonly': True,
    },
    'publish_readiness': {
        'desc': (
            'Read-only: publish checklist for one offering — state counts, '
            'submitted-but-unverified, verified-ready-to-publish, entries '
            'missing grades/scales, maker-checker notes.'
        ),
        'args': ['offering_id'],
        'readonly': True,
    },
}

_TOOL_NAMES = set(TOOL_SPECS)

# Templates per assignment type (mirrors the selection on
# ``edicai.assignment.assignment_type``). Weights sum to 100.
_RUBRIC_TEMPLATES = {
    'homework': [
        ('Conceptual Accuracy',
         'Correctness of the concepts applied in each answer.', 40.0),
        ('Completeness',
         'All questions attempted with full working shown.', 30.0),
        ('Clarity & Presentation',
         'Readable structure, notation and presentation.', 20.0),
        ('Referencing & Timeliness',
         'Sources cited where needed; submitted on time.', 10.0),
    ],
    'project': [
        ('Problem Analysis & Design',
         'Problem framing, requirements and design quality.', 25.0),
        ('Implementation',
         'Working solution, code/artefact quality.', 30.0),
        ('Testing & Validation',
         'Evidence of testing and validation of results.', 20.0),
        ('Documentation',
         'Report clarity, structure and reproducibility.', 15.0),
        ('Presentation & Viva',
         'Demo clarity and answers to questions.', 10.0),
    ],
    'lab': [
        ('Procedure & Safety',
         'Correct procedure followed; safety norms observed.', 20.0),
        ('Observations & Data',
         'Accurate recording of observations and data.', 30.0),
        ('Analysis & Calculations',
         'Correct analysis, graphs and calculations.', 30.0),
        ('Conclusion & Viva',
         'Valid conclusions; answers during viva.', 20.0),
    ],
    'quiz': [
        ('Conceptual Accuracy',
         'Correct answers to concept questions.', 50.0),
        ('Application',
         'Correct application to problems/scenarios.', 30.0),
        ('Completeness',
         'All items attempted within the time allowed.', 20.0),
    ],
}

_ASSIGNMENT_TYPES = ('homework', 'project', 'lab', 'quiz')


class GradeCopilot(models.AbstractModel):
    """Suggest-only grading assistant. Reads state, never changes it."""

    _name = 'grading.ai.copilot'
    _description = 'Grade Copilot (suggest-only AI tools)'

    # ------------------------------------------------------------------
    # Dispatcher + shared helpers
    # ------------------------------------------------------------------

    @api.model
    def run_tool(self, name, **kwargs):
        """Dispatch ONLY to tools declared in TOOL_SPECS."""
        if name not in _TOOL_NAMES:
            raise UserError(_('Unknown copilot tool: %s.') % name)
        handler = getattr(self, '_tool_%s' % name, None)
        if handler is None:
            raise UserError(_('Copilot tool not implemented: %s.') % name)
        return handler(**kwargs)

    @api.model
    def _company_id(self):
        return self.env.company.id

    @api.model
    def _scoped_offering(self, offering_id):
        """Fetch one course offering scoped to the current company."""
        if not offering_id:
            raise UserError(_('Provide offering_id.'))
        Offering = self.env['edicai.course.offering']
        offering = Offering.browse(int(offering_id))
        if not offering.exists():
            raise UserError(_('Course offering not found.'))
        offering.check_access('read')
        if offering.company_id.id != self._company_id():
            raise UserError(_(
                'Course offering belongs to another institution.',
            ))
        return offering

    @api.model
    def _scoped_scale(self, scale_id=None):
        """Default company scale, or the requested scale if it belongs
        to the current company."""
        Scale = self.env['edicai.grade.scale']
        if scale_id:
            scale = Scale.browse(int(scale_id))
            if not scale.exists():
                raise UserError(_('Grade scale not found.'))
            scale.check_access('read')
            if scale.company_id.id != self._company_id():
                raise UserError(_(
                    'Grade scale belongs to another institution.',
                ))
            return scale
        return Scale.get_default_scale(self._company_id())

    @api.model
    def _offering_entries(self, offering):
        Entry = self.env['edicai.grade.entry']
        return Entry.search([
            ('course_offering_id', '=', offering.id),
            ('company_id', '=', self._company_id()),
        ])

    # ------------------------------------------------------------------
    # Draft tool — rubric suggestion (never creates anything)
    # ------------------------------------------------------------------

    @api.model
    def _tool_rubric_suggest(self, scale_id=None, assignment_type=None,
                             max_marks=None, assignment_id=None):
        """Draft a criterion list from the scale + assignment type.

        Read-only: inspects the grade scale lines and (optionally) one
        assignment for context. Returns a plain-dict draft for HUMAN
        review — it never creates ``edicai.assignment.rubric`` or
        ``edicai.assignment.rubric.criterion`` records and never writes
        on the assignment.
        """
        atype = (assignment_type or 'homework').strip().lower()
        if atype not in _ASSIGNMENT_TYPES:
            raise UserError(_(
                'Unknown assignment_type "%s". Choose one of: %s.',
            ) % (assignment_type, ', '.join(_ASSIGNMENT_TYPES)))

        scale = self._scoped_scale(scale_id)
        scale_lines = []
        if scale:
            scale.check_access('read')
            for line in scale.line_ids.sorted('min_percentage'):
                scale_lines.append({
                    'letter_grade': line.letter_grade,
                    'min_percentage': line.min_percentage,
                    'max_percentage': line.max_percentage,
                    'grade_point': line.grade_point,
                    'is_passing': line.is_passing,
                })

        # Optional assignment context (read-only).
        assignment_ctx = False
        Assignment = self.env.get('edicai.assignment')
        if assignment_id and Assignment is not None:
            assignment = Assignment.browse(int(assignment_id))
            if assignment.exists():
                assignment.check_access('read')
                if (not atype or assignment_type is None) \
                        and assignment.assignment_type in _ASSIGNMENT_TYPES:
                    atype = assignment.assignment_type
                rubric = assignment.rubric_id
                assignment_ctx = {
                    'assignment_id': assignment.id,
                    'title': assignment.title,
                    'assignment_type': assignment.assignment_type,
                    'max_marks': assignment.max_marks,
                    'has_rubric': bool(rubric),
                    'rubric_name': rubric.name if rubric else False,
                    'existing_criteria': [
                        {'name': c.name,
                         'max_points': c.max_points}
                        for c in rubric.criterion_ids
                    ] if rubric else [],
                }
                if max_marks is None:
                    max_marks = assignment.max_marks

        total = float(max_marks) if max_marks else 0.0
        criteria = []
        template = _RUBRIC_TEMPLATES[atype]
        for idx, (cname, cdesc, weight) in enumerate(template):
            points = round(total * weight / 100.0, 2) if total > 0 else 0.0
            # Absorb rounding residue on the last criterion so the
            # suggested points sum exactly to max_marks.
            if total > 0 and idx == len(template) - 1:
                so_far = sum(c['suggested_points'] for c in criteria)
                points = round(total - so_far, 2)
            criteria.append({
                'sequence': (idx + 1) * 10,
                'name': cname,
                'description': cdesc,
                'weight_pct': weight,
                'suggested_points': points,
                'is_bonus': False,
            })

        return {
            'type': 'rubric_suggest_draft',
            'assignment_type': atype,
            'max_marks': total,
            'scale_id': scale.id if scale else False,
            'scale_name': scale.name if scale else False,
            'scale_lines': scale_lines,
            'assignment_context': assignment_ctx,
            'criteria': criteria,
            'criteria_total': round(
                sum(c['suggested_points'] for c in criteria), 2,
            ),
            'requires_human_review': True,
            'warning': _(
                'DRAFT ONLY — no rubric was created. A faculty member '
                'must review, adjust and create the rubric manually.',
            ),
        }

    # ------------------------------------------------------------------
    # Read-only tool — anomaly flags (neutral language only)
    # ------------------------------------------------------------------

    @api.model
    def _tool_anomaly_flags(self, offering_id, threshold_std=2.0,
                            basis='total'):
        """Flag statistical outliers and max/min clusters for review.

        Read-only: aggregates ``edicai.grade.entry`` values for one
        offering. Reasons are phrased neutrally ("suggested for human
        review") — this tool never uses judgement language and never
        touches ``entry_state`` or any marks field.
        """
        offering = self._scoped_offering(offering_id)
        try:
            threshold = float(threshold_std or 2.0)
        except (TypeError, ValueError):
            threshold = 2.0
        threshold = max(1.0, min(threshold, 3.0))
        if basis not in ('total', 'percentage', 'internal', 'external'):
            raise UserError(_(
                'Unknown basis "%s". Use total, percentage, internal '
                'or external.', ) % basis)
        field = {
            'total': 'total_marks_obtained',
            'percentage': 'percentage',
            'internal': 'internal_marks',
            'external': 'external_marks',
        }[basis]

        entries = self._offering_entries(offering)
        values = [(e, float(e[field] or 0.0)) for e in entries]
        count = len(values)
        if not count:
            return {
                'offering_id': offering.id,
                'offering_name': offering.display_name,
                'basis': basis,
                'count': 0,
                'flags': [],
                'note': _('No grade entries found for this offering.'),
            }
        mean = sum(v for _, v in values) / count
        variance = sum((v - mean) ** 2 for _, v in values) / count
        std = math.sqrt(variance)
        vmax = max(v for _, v in values)
        vmin = min(v for _, v in values)
        at_max = sum(1 for _, v in values if v == vmax)
        at_min = sum(1 for _, v in values if v == vmin)

        flags = []
        for entry, val in values:
            z = (val - mean) / std if std > 0 else 0.0
            reasons = []
            if std > 0 and abs(z) > threshold:
                direction = _('above') if z > 0 else _('below')
                reasons.append(_(
                    '%.2f standard deviations %s the offering mean '
                    '(%.2f) — suggested for human review.',
                ) % (abs(z), direction, mean))
            if count > 1 and val == vmax and at_max >= 2:
                reasons.append(_(
                    'Part of a cluster of %d entries at the highest '
                    'observed value (%.2f) — suggested for human '
                    'review.', ) % (at_max, vmax))
            if count > 1 and val == vmin and at_min >= 2:
                reasons.append(_(
                    'Part of a cluster of %d entries at the lowest '
                    'observed value (%.2f) — suggested for human '
                    'review.', ) % (at_min, vmin))
            if reasons:
                flags.append({
                    'grade_entry_id': entry.id,
                    'student_name': entry.student_id.display_name,
                    'value': val,
                    'z_score': round(z, 2),
                    'entry_state': entry.entry_state,
                    'reasons': reasons,
                })
        flags.sort(key=lambda f: abs(f['z_score']), reverse=True)
        return {
            'offering_id': offering.id,
            'offering_name': offering.display_name,
            'basis': basis,
            'count': count,
            'mean': round(mean, 2),
            'std': round(std, 2),
            'min': vmin,
            'max': vmax,
            'at_max_count': at_max,
            'at_min_count': at_min,
            'threshold_std': threshold,
            'flags': flags,
            'flagged_count': len(flags),
            'review_note': _(
                'Flags are statistical observations only, not findings. '
                'A faculty member must review each flagged entry; this '
                'tool never changes grades or states.',
            ),
        }

    # ------------------------------------------------------------------
    # Read-only tool — gradebook preview (recompute, never write)
    # ------------------------------------------------------------------

    @api.model
    def _tool_gradebook_preview(self, offering_id):
        """Recompute the roll-up read-only and diff against current
        ``internal_marks``.

        Mirrors the ``edicai.gradebook.student.line`` formula::

            assignment_percentage =
                sum(marks_obtained) / sum(max_marks) * 100
            computed_component =
                max_ca_marks * (weight / 100) * (percentage / 100)

        capped at ``max_ca_marks``. Reads gradebook config, graded
        submissions and grade entries; writes nothing and never calls
        ``action_apply_ca_marks`` / ``action_apply_line``.
        """
        offering = self._scoped_offering(offering_id)
        company_id = self._company_id()

        weight = 100.0
        max_ca = 0.0
        config_found = False
        Config = self.env.get('edicai.gradebook.config')
        if Config is not None:
            config = Config.search([
                ('course_offering_id', '=', offering.id),
                ('company_id', '=', company_id),
            ], limit=1)
            if config:
                config.check_access('read')
                weight = config.assignment_weight_pct or 0.0
                max_ca = config.max_ca_marks or 0.0
                config_found = True
        if not config_found:
            course = offering.course_id
            if course:
                try:
                    max_ca = float(
                        course.internal_assessment_marks or 0.0)
                except Exception:
                    max_ca = 0.0

        Submission = self.env.get('edicai.assignment.submission')
        graded_by_student = {}
        if Submission is not None:
            graded = Submission.search([
                ('course_offering_id', '=', offering.id),
                ('company_id', '=', company_id),
                ('state', '=', 'graded'),
            ])
            for sub in graded:
                try:
                    sub.check_access('read')
                except Exception:
                    continue
                amax = 0.0
                try:
                    amax = float(sub.assignment_id.max_marks or 0.0)
                except Exception:
                    amax = 0.0
                graded_by_student.setdefault(
                    sub.student_id.id, []).append(
                        (float(sub.marks_obtained or 0.0), amax))

        entries = self._offering_entries(offering)
        by_enrollment = {e.enrollment_id.id: e for e in entries}

        Enrollment = self.env['edicai.enrollment']
        enrollments = Enrollment.search([
            ('course_offering_id', '=', offering.id),
            ('company_id', '=', company_id),
            ('enrollment_state', 'in', ('registered', 'completed')),
        ])

        rows = []
        for enr in enrollments:
            subs = graded_by_student.get(enr.student_id.id, [])
            obtained = sum(m for m, _ in subs)
            possible = sum(m for _, m in subs)
            pct = round(obtained * 100.0 / possible, 2) if possible else 0.0
            component = round(max_ca * (weight / 100.0) * (pct / 100.0), 2)
            if max_ca:
                component = min(component, max_ca)
            else:
                component = 0.0
            entry = by_enrollment.get(enr.id)
            current = float(
                entry.internal_marks) if entry else False
            delta = round(component - current, 2) \
                if entry else False
            editable = bool(
                entry and entry.entry_state in ('draft', 'submitted'))
            rows.append({
                'enrollment_id': enr.id,
                'student_id': enr.student_id.id,
                'student_name': enr.student_id.display_name,
                'graded_submissions': len(subs),
                'assignment_percentage': pct,
                'computed_component': component,
                'current_internal_marks': current,
                'delta': delta,
                'grade_entry_id': entry.id if entry else False,
                'grade_entry_state':
                    entry.entry_state if entry else False,
                'would_update': bool(
                    editable and delta not in (False, 0.0)),
                'in_sync': bool(
                    entry and delta == 0.0),
                'blocked_reason': (
                    False if not entry else
                    False if editable else
                    _('Grade entry is %s; only draft/submitted '
                      'entries accept CA updates.') % entry.entry_state
                ) if entry else _('No grade entry yet.'),
            })

        would_update = sum(1 for r in rows if r['would_update'])
        in_sync = sum(1 for r in rows if r['in_sync'])
        blocked = sum(1 for r in rows
                      if r['grade_entry_id'] and r['blocked_reason'])
        missing = sum(1 for r in rows if not r['grade_entry_id'])
        return {
            'offering_id': offering.id,
            'offering_name': offering.display_name,
            'gradebook_config_found': config_found,
            'assignment_weight_pct': weight,
            'max_ca_marks': max_ca,
            'rows': rows,
            'summary': {
                'students': len(rows),
                'would_update': would_update,
                'in_sync': in_sync,
                'blocked_by_state': blocked,
                'missing_entry': missing,
            },
            'warning': _(
                'PREVIEW ONLY — nothing was written. Applying these '
                'values remains a human action via the gradebook.',
            ),
        }

    # ------------------------------------------------------------------
    # Read-only tool — publish readiness checklist
    # ------------------------------------------------------------------

    @api.model
    def _tool_publish_readiness(self, offering_id):
        """Checklist for one offering: state counts, unverified work,
        missing grades/scales. Read-only — never submits, verifies,
        publishes or locks anything."""
        offering = self._scoped_offering(offering_id)
        entries = self._offering_entries(offering)

        by_state = {}
        for state, _label in self.env['edicai.grade.entry']._fields[
                'entry_state'].selection:
            by_state[state] = 0
        for entry in entries:
            by_state[entry.entry_state] = \
                by_state.get(entry.entry_state, 0) + 1

        submitted = entries.filtered(
            lambda e: e.entry_state == 'submitted')
        verified = entries.filtered(
            lambda e: e.entry_state == 'verified')
        missing_grades = entries.filtered(lambda e: not e.letter_grade)

        default_scale = self.env['edicai.grade.scale'].get_default_scale(
            self._company_id())
        if default_scale:
            missing_scales = entries.filtered(
                lambda e: not e.grade_scale_id and not e.letter_grade)
            # Entries without an explicit scale fall back to the company
            # default, so only ungraded ones are truly scale-blocked.
        else:
            missing_scales = entries.filtered(
                lambda e: not e.grade_scale_id)

        own_pending = submitted.filtered(
            lambda e: e.create_uid.id == self.env.uid)
        credits_done = entries.filtered(lambda e: e.credits_applied)

        checklist = [
            {
                'item': 'no_drafts',
                'label': _('No entries left in Draft'),
                'passed': by_state.get('draft', 0) == 0,
                'detail': _('%d draft entries.') % by_state.get(
                    'draft', 0),
            },
            {
                'item': 'nothing_awaiting_verification',
                'label': _('Nothing awaiting verification '
                           '(submitted → verified)'),
                'passed': len(submitted) == 0,
                'detail': _('%d submitted-but-unverified entries.') % len(
                    submitted),
            },
            {
                'item': 'all_have_grades',
                'label': _('Every entry has marks and a letter grade'),
                'passed': len(missing_grades) == 0,
                'detail': _('%d entries missing marks/letter grade.') % len(
                    missing_grades),
            },
            {
                'item': 'scales_resolved',
                'label': _('Grade scales resolved (explicit or default)'),
                'passed': len(missing_scales) == 0,
                'detail': _('%d entries missing a usable scale.') % len(
                    missing_scales),
            },
            {
                'item': 'verified_ready',
                'label': _('Verified entries ready to publish'),
                'passed': len(verified) > 0,
                'detail': _('%d verified entries ready to publish.') % len(
                    verified),
            },
        ]
        blockers = [c['label'] + ' — ' + c['detail']
                    for c in checklist
                    if not c['passed'] and c['item'] != 'verified_ready']
        ready = not blockers and len(verified) > 0

        return {
            'offering_id': offering.id,
            'offering_name': offering.display_name,
            'total_entries': len(entries),
            'by_state': by_state,
            'submitted_but_unverified': len(submitted),
            'verified_ready_to_publish': len(verified),
            'missing_grades_count': len(missing_grades),
            'missing_grades_ids': missing_grades.ids,
            'missing_scales_count': len(missing_scales),
            'missing_scales_ids': missing_scales.ids,
            'default_scale_id':
                default_scale.id if default_scale else False,
            'default_scale_name':
                default_scale.name if default_scale else False,
            'own_submitted_count': len(own_pending),
            'maker_checker_note': _(
                '%d submitted entries were created by you; maker-checker '
                'rules mean another registrar/manager/admin must verify '
                'them — the copilot never verifies.') % len(own_pending),
            'credits_applied_count': len(credits_done),
            'checklist': checklist,
            'blockers': blockers,
            'ready_to_publish': ready,
        }
