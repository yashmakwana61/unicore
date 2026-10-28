"""
Timetable Optimizer Copilot — read-only scheduling analysis.

Suggest-only assistant over ``edicai.timetable.entry``. Every tool READS;
nothing here ever creates, writes, unlinks, confirms, cancels, or posts
on any record. ``move_suggest`` returns draft alternatives for a HUMAN
to apply through the normal timetable UI (which re-runs the model
constraints).

Conflict logic mirrors
``edicai_timetable/models/edicai_timetable_entry.py`` exactly:

* ``_date_ranges_overlap``: missing dates count as overlapping;
  otherwise ``start1 <= end2 and start2 <= end1``.
* ``_time_ranges_overlap``: missing times count as overlapping;
  otherwise ``s1 < e2 and s2 < e1`` (float hours from
  ``edicai.time.slot.start_time`` / ``end_time``).
* A clash needs: same ``day_of_week`` + date overlap + time overlap +
  shared room OR shared instructor OR shared offering, with cancelled
  entries ignored.

Scope: every search is forced to the requester's company
(``env.company``) and runs as the current user so record rules apply.
An optional ``campus_id`` narrows further where the target model has a
``campus_id`` field. No privilege elevation is used anywhere.

Wiring (manual step — existing files are intentionally untouched):

* add ``from . import ai_tools_timetable`` to
  ``edicai_timetable/models/__init__.py``;
* add ``data/ai_copilot_prompts.xml`` to the manifest ``data`` list.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# System-prompt storage key (seeded by data/ai_copilot_prompts.xml).
SCHEDULER_PROMPT_PARAM = 'edicai_timetable.scheduler_system_prompt'

DEFAULT_SYSTEM_PROMPT = (
    'You are the Timetable Optimizer, a suggest-only scheduling '
    'assistant. Use clash_scan, room_load, faculty_load and move_suggest '
    'to analyse. Prefer minimal moves, respect room capacity, and never '
    'apply changes — a human applies them.'
)

TOOL_SPECS = {
    'clash_scan': {
        'desc': (
            'Read-only: scan timetable entries for room / instructor / '
            'section clashes using the model time-range overlap logic. '
            'Narrow with offering/day/slot/room/instructor, or full-table '
            'scan per semester. Company-scoped.'
        ),
        'args': [
            'semester_id', 'offering_id', 'day_of_week', 'time_slot_id',
            'room_id', 'instructor_id', 'campus_id', 'limit',
        ],
        'params': {
            'semester_id': 'Optional semester id for a full-table scan.',
            'offering_id': 'Optional course offering id to narrow the scan.',
            'day_of_week': 'Optional day 0 (Monday) to 6 (Sunday).',
            'time_slot_id': 'Optional time slot id to narrow the scan.',
            'room_id': 'Optional room id to narrow the scan.',
            'instructor_id': 'Optional instructor (edicai.faculty.member) id.',
            'campus_id': 'Optional campus id (applied where supported).',
            'limit': 'Max pairs returned (default 100, max 500).',
        },
        'readonly': True,
    },
    'room_load': {
        'desc': (
            'Read-only: utilization per room per day '
            '(sessions, booked minutes, utilization %). Company-scoped.'
        ),
        'args': ['semester_id', 'campus_id', 'day_of_week'],
        'params': {
            'semester_id': 'Optional semester id to scope entries.',
            'campus_id': 'Optional campus id to scope rooms/entries.',
            'day_of_week': 'Optional single day 0-6; default all days.',
        },
        'readonly': True,
    },
    'faculty_load': {
        'desc': (
            'Read-only: teaching hours per instructor per week '
            '(sessions, minutes, hours, per-day split). Company-scoped.'
        ),
        'args': ['semester_id', 'campus_id', 'instructor_id'],
        'params': {
            'semester_id': 'Optional semester id to scope entries.',
            'campus_id': 'Optional campus id to scope entries.',
            'instructor_id': 'Optional single instructor id.',
        },
        'readonly': True,
    },
    'move_suggest': {
        'desc': (
            'DRAFT ONLY: for one clashed entry propose up to 3 free '
            'room/slot alternatives with reasons. Never applies anything; '
            'a human must confirm via the timetable UI.'
        ),
        'args': ['entry_id', 'max_suggestions'],
        'params': {
            'entry_id': 'Database id of the edicai.timetable.entry record.',
            'max_suggestions': 'Max alternatives (default 3, max 5).',
        },
        'readonly': True,
        'draft': True,
    },
}

_DAY_LABELS = {
    '0': 'Monday',
    '1': 'Tuesday',
    '2': 'Wednesday',
    '3': 'Thursday',
    '4': 'Friday',
    '5': 'Saturday',
    '6': 'Sunday',
}


class TimetableAICopilot(models.AbstractModel):
    """Timetable Optimizer Copilot — analysis only, zero writes."""

    _name = 'timetable.ai.copilot'
    _description = 'Timetable Optimizer Copilot (read-only AI tools)'

    # ------------------------------------------------------------------
    # Registry / chat entry
    # ------------------------------------------------------------------

    @api.model
    def get_tool_specs(self):
        """Return the TOOL_SPECS registry for the AI orchestrator."""
        return TOOL_SPECS

    @api.model
    def _get_system_prompt(self):
        stored = self.env['ir.config_parameter'].get_param(
            SCHEDULER_PROMPT_PARAM, default='',
        )
        return stored or DEFAULT_SYSTEM_PROMPT

    @api.model
    def chat(self, prompt):
        """One-shot question answering with the scheduler system prompt."""
        if not prompt:
            raise UserError(_('Please provide a question for the optimizer.'))
        provider = self.env['edicai.ai.provider']
        return provider.generate_text(
            prompt, system_prompt=self._get_system_prompt(),
        )

    @api.model
    def check_tool_access(self, tool_name):
        """Allow-list gate; reads rely on record rules on top."""
        if tool_name not in TOOL_SPECS:
            raise UserError(_('Unknown copilot tool: %s.') % tool_name)
        self.env['edicai.timetable.entry'].check_access('read')
        return True

    # ------------------------------------------------------------------
    # Shared helpers (pure reads, same overlap math as the entry model)
    # ------------------------------------------------------------------

    @api.model
    def _date_ranges_overlap(self, start1, end1, start2, end2):
        if not all([start1, end1, start2, end2]):
            return True
        return start1 <= end2 and start2 <= end1

    @api.model
    def _time_ranges_overlap(self, s1, e1, s2, e2):
        if not all([
                s1 is not None, e1 is not None,
                s2 is not None, e2 is not None,
        ]):
            return True
        return s1 < e2 and s2 < e1

    @api.model
    def _serialize_entry(self, entry):
        slot = entry.time_slot_id
        return {
            'id': entry.id,
            'display_name': entry.display_name,
            'offering_id': entry.course_offering_id.id
            if entry.course_offering_id else False,
            'offering_name': entry.course_offering_id.display_name
            if entry.course_offering_id else False,
            'semester_id': entry.semester_id.id
            if entry.semester_id else False,
            'day_of_week': entry.day_of_week,
            'day_label': _DAY_LABELS.get(entry.day_of_week or '', ''),
            'time_slot_id': slot.id if slot else False,
            'time_slot_name': slot.display_label if slot else False,
            'start_time': slot.start_time if slot else False,
            'end_time': slot.end_time if slot else False,
            'duration_minutes': slot.duration_minutes if slot else 0,
            'room_id': entry.room_id.id if entry.room_id else False,
            'room_name': entry.room_id.display_name
            if entry.room_id else False,
            'room_capacity': entry.room_id.capacity
            if entry.room_id else False,
            'instructor_id': entry.instructor_id.id
            if entry.instructor_id else False,
            'instructor_name': entry.instructor_id.display_name
            if entry.instructor_id else False,
            'entry_state': entry.entry_state,
            'effective_date_start': str(entry.effective_date_start)
            if entry.effective_date_start else False,
            'effective_date_end': str(entry.effective_date_end)
            if entry.effective_date_end else False,
        }

    @api.model
    def view_schedule(self, schedule_date=None, limit=50):
        """Read recurring timetable entries active on one calendar date.

        Date/day selection is performed by the application. Company scope
        and current-user ACL/record rules remain authoritative; this is a
        read-only schedule view, distinct from ``clash_scan``.
        """
        Entry = self.env['edicai.timetable.entry']
        Entry.check_access('read')
        requested_date = fields.Date.context_today(self)
        if schedule_date in ('today', 'tomorrow', 'yesterday'):
            requested_date += timedelta(days={
                'today': 0, 'tomorrow': 1, 'yesterday': -1,
            }[schedule_date])
        elif schedule_date:
            requested_date = fields.Date.to_date(schedule_date)
        try:
            limit = max(1, min(int(limit or 50), 100))
        except (TypeError, ValueError):
            limit = 50
        domain = self._scan_domain(day_of_week=str(requested_date.weekday()))
        domain += [
            ('entry_state', '!=', 'cancelled'),
            '|', ('effective_date_start', '=', False),
                 ('effective_date_start', '<=', requested_date),
            '|', ('effective_date_end', '=', False),
                 ('effective_date_end', '>=', requested_date),
        ]
        total = Entry.search_count(domain)
        entries = Entry.search(domain, order='day_of_week, time_slot_id',
                               limit=limit)
        return {
            'date': fields.Date.to_string(requested_date),
            'count': total,
            'entries': [self._serialize_entry(entry) for entry in entries],
            'truncated': total > len(entries),
            'shown': len(entries),
        }

    @api.model
    def _pair_clash_types(self, first, second):
        """Return clash kinds between two entries (room/instructor/section).

        Same preconditions as ``_check_scheduling_conflicts``: same day,
        overlapping effective dates, overlapping slot time ranges.
        """
        if first.day_of_week != second.day_of_week:
            return []
        if not self._date_ranges_overlap(
                first.effective_date_start, first.effective_date_end,
                second.effective_date_start, second.effective_date_end):
            return []
        s1 = first.time_slot_id.start_time \
            if first.time_slot_id else None
        e1 = first.time_slot_id.end_time \
            if first.time_slot_id else None
        s2 = second.time_slot_id.start_time \
            if second.time_slot_id else None
        e2 = second.time_slot_id.end_time \
            if second.time_slot_id else None
        if not self._time_ranges_overlap(s1, e1, s2, e2):
            return []
        kinds = []
        if first.room_id and second.room_id \
                and first.room_id.id == second.room_id.id:
            kinds.append('room')
        if first.instructor_id and second.instructor_id \
                and first.instructor_id.id == second.instructor_id.id:
            kinds.append('instructor')
        if first.course_offering_id and second.course_offering_id \
                and first.course_offering_id.id == \
                second.course_offering_id.id:
            kinds.append('section')
        return kinds

    @api.model
    def _scan_domain(self, semester_id=None, offering_id=None,
                     day_of_week=None, time_slot_id=None, room_id=None,
                     instructor_id=None, campus_id=None):
        company_id = self.env.company.id
        domain = [
            ('company_id', '=', company_id),
            ('entry_state', '!=', 'cancelled'),
        ]
        if semester_id:
            domain.append(('semester_id', '=', int(semester_id)))
        if offering_id:
            domain.append(('course_offering_id', '=', int(offering_id)))
        if day_of_week in ('0', '1', '2', '3', '4', '5', '6',
                           0, 1, 2, 3, 4, 5, 6):
            domain.append(('day_of_week', '=', str(day_of_week)))
        if time_slot_id:
            domain.append(('time_slot_id', '=', int(time_slot_id)))
        if room_id:
            domain.append(('room_id', '=', int(room_id)))
        if instructor_id:
            domain.append(('instructor_id', '=', int(instructor_id)))
        if campus_id:
            domain.append(('campus_id', '=', int(campus_id)))
        return domain

    # ------------------------------------------------------------------
    # Tool: clash_scan
    # ------------------------------------------------------------------

    @api.model
    def clash_scan(self, semester_id=None, offering_id=None,
                   day_of_week=None, time_slot_id=None, room_id=None,
                   instructor_id=None, campus_id=None, limit=100):
        """Pairwise clash scan over the scoped entry set."""
        self.check_tool_access('clash_scan')
        try:
            limit = int(limit or 100)
        except (TypeError, ValueError):
            limit = 100
        limit = max(1, min(limit, 500))
        domain = self._scan_domain(
            semester_id=semester_id, offering_id=offering_id,
            day_of_week=day_of_week, time_slot_id=time_slot_id,
            room_id=room_id, instructor_id=instructor_id,
            campus_id=campus_id,
        )
        entries = self.env['edicai.timetable.entry'].search(
            domain, order='day_of_week, time_slot_id',
        )
        pairs = []
        ids = entries.ids
        for pos, first in enumerate(entries):
            for second in entries[pos + 1:]:
                kinds = self._pair_clash_types(first, second)
                for kind in kinds:
                    if kind == 'room':
                        reason = _(
                            'Room "%s" double-booked on %s (%s overlaps %s).'
                        ) % (
                            first.room_id.display_name,
                            _DAY_LABELS.get(first.day_of_week, ''),
                            first.time_slot_id.display_label,
                            second.time_slot_id.display_label,
                        )
                    elif kind == 'instructor':
                        reason = _(
                            'Instructor "%s" double-booked on %s (%s overlaps %s).'
                        ) % (
                            first.instructor_id.display_name,
                            _DAY_LABELS.get(first.day_of_week, ''),
                            first.time_slot_id.display_label,
                            second.time_slot_id.display_label,
                        )
                    else:
                        reason = _(
                            'Offering "%s" has two classes overlapping on %s '
                            '(%s overlaps %s).'
                        ) % (
                            first.course_offering_id.display_name,
                            _DAY_LABELS.get(first.day_of_week, ''),
                            first.time_slot_id.display_label,
                            second.time_slot_id.display_label,
                        )
                    pairs.append({
                        'type': kind,
                        'entry_a': self._serialize_entry(first),
                        'entry_b': self._serialize_entry(second),
                        'reason': reason,
                    })
                    if len(pairs) >= limit:
                        break
                if len(pairs) >= limit:
                    break
            if len(pairs) >= limit:
                break
        _logger.info(
            'Timetable optimizer clash_scan: %d entries, %d pairs '
            '(company=%s).', len(ids), len(pairs), self.env.company.id,
        )
        return {
            'company_id': self.env.company.id,
            'company_name': self.env.company.display_name,
            'scanned_entries': len(ids),
            'clash_count': len(pairs),
            'pairs': pairs,
            'truncated': len(pairs) >= limit,
        }

    # ------------------------------------------------------------------
    # Tool: room_load
    # ------------------------------------------------------------------

    @api.model
    def room_load(self, semester_id=None, campus_id=None,
                  day_of_week=None):
        """Utilization per room per day from the scoped entries."""
        self.check_tool_access('room_load')
        company = self.env.company
        room_domain = [('company_id', '=', company.id)]
        if campus_id:
            room_domain.append(('campus_id', '=', int(campus_id)))
        rooms = self.env['edicai.room'].search(
            room_domain, order='code',
        )
        slot_domain = [('company_id', '=', company.id)]
        slots = self.env['edicai.time.slot'].search(slot_domain)
        teach_slots = slots.filtered(lambda s: not s.is_break)
        denom_slots = teach_slots or slots
        denom_minutes = sum(s.duration_minutes for s in denom_slots)
        denom_count = len(denom_slots)

        entry_domain = self._scan_domain(
            semester_id=semester_id, campus_id=campus_id,
            day_of_week=day_of_week,
        )
        entries = self.env['edicai.timetable.entry'].search(entry_domain)
        days = [str(day_of_week)] if day_of_week in (
            '0', '1', '2', '3', '4', '5', '6',
            0, 1, 2, 3, 4, 5, 6,
        ) else ['0', '1', '2', '3', '4', '5', '6']

        rows = []
        for room in rooms:
            for day in days:
                booked = entries.filtered(
                    lambda e, r=room, d=day: e.room_id.id == r.id
                    and e.day_of_week == d,
                )
                minutes = sum(
                    e.time_slot_id.duration_minutes
                    for e in booked if e.time_slot_id
                )
                util = round(100.0 * minutes / denom_minutes, 1) \
                    if denom_minutes else 0.0
                rows.append({
                    'room_id': room.id,
                    'room_code': room.code,
                    'room_name': room.display_name,
                    'room_capacity': room.capacity,
                    'room_state': room.room_state,
                    'day_of_week': day,
                    'day_label': _DAY_LABELS.get(day, ''),
                    'booked_sessions': len(booked),
                    'booked_minutes': minutes,
                    'total_slots': denom_count,
                    'total_slot_minutes': denom_minutes,
                    'utilization_pct': util,
                })
        rows.sort(key=lambda r: (r['room_code'] or '', r['day_of_week']))
        return {
            'company_id': company.id,
            'semester_id': int(semester_id) if semester_id else False,
            'denominator_slots': denom_count,
            'denominator_minutes': denom_minutes,
            'rows': rows,
            'row_count': len(rows),
        }

    # ------------------------------------------------------------------
    # Tool: faculty_load
    # ------------------------------------------------------------------

    @api.model
    def faculty_load(self, semester_id=None, campus_id=None,
                     instructor_id=None):
        """Weekly teaching load per instructor from scoped entries."""
        self.check_tool_access('faculty_load')
        entry_domain = self._scan_domain(
            semester_id=semester_id, campus_id=campus_id,
            instructor_id=instructor_id,
        )
        entries = self.env['edicai.timetable.entry'].search(entry_domain)
        buckets = {}
        for entry in entries:
            if not entry.instructor_id:
                continue
            key = entry.instructor_id.id
            bucket = buckets.setdefault(key, {
                'instructor_id': key,
                'instructor_name':
                    entry.instructor_id.display_name,
                'sessions': 0,
                'minutes': 0,
                'per_day': {day: {'sessions': 0, 'minutes': 0}
                            for day in _DAY_LABELS},
            })
            minutes = entry.time_slot_id.duration_minutes \
                if entry.time_slot_id else 0
            bucket['sessions'] += 1
            bucket['minutes'] += minutes
            day_bucket = bucket['per_day'].get(entry.day_of_week)
            if day_bucket is not None:
                day_bucket['sessions'] += 1
                day_bucket['minutes'] += minutes
        rows = []
        for bucket in buckets.values():
            per_day = [
                {
                    'day_of_week': day,
                    'day_label': _DAY_LABELS[day],
                    'sessions': vals['sessions'],
                    'minutes': vals['minutes'],
                    'hours': round(vals['minutes'] / 60.0, 2),
                }
                for day, vals in sorted(bucket['per_day'].items())
                if vals['sessions']
            ]
            rows.append({
                'instructor_id': bucket['instructor_id'],
                'instructor_name': bucket['instructor_name'],
                'weekly_sessions': bucket['sessions'],
                'weekly_minutes': bucket['minutes'],
                'weekly_hours': round(bucket['minutes'] / 60.0, 2),
                'per_day': per_day,
            })
        rows.sort(key=lambda r: r['instructor_name'] or '')
        return {
            'company_id': self.env.company.id,
            'semester_id': int(semester_id) if semester_id else False,
            'instructors': rows,
            'count': len(rows),
        }

    # ------------------------------------------------------------------
    # Tool: move_suggest (drafts only — zero writes)
    # ------------------------------------------------------------------

    @api.model
    def _candidate_is_free(self, entry, day, slot, room, scope_entries):
        """True when (day, slot, room) keeps entry clash-free.

        Checks the in-memory scoped set for room/instructor/section
        overlap plus ad-hoc room bookings for the candidate room/day.
        Read-only; never writes.
        """
        for other in scope_entries:
            if other.id == entry.id:
                continue
            if other.day_of_week != day:
                continue
            if not self._date_ranges_overlap(
                    entry.effective_date_start,
                    entry.effective_date_end,
                    other.effective_date_start,
                    other.effective_date_end):
                continue
            if not self._time_ranges_overlap(
                    slot.start_time, slot.end_time,
                    other.time_slot_id.start_time if other.time_slot_id
                    else None,
                    other.time_slot_id.end_time if other.time_slot_id
                    else None):
                continue
            if other.room_id and room and other.room_id.id == room.id:
                return False
            if other.instructor_id and entry.instructor_id \
                    and other.instructor_id.id == entry.instructor_id.id:
                return False
            if other.course_offering_id and entry.course_offering_id \
                    and other.course_offering_id.id == \
                    entry.course_offering_id.id:
                return False
        bookings = self.env['edicai.room.booking'].search([
            ('company_id', '=', self.env.company.id),
            ('room_id', '=', room.id),
            ('day_of_week', '=', day),
            ('booking_state', '!=', 'cancelled'),
        ])
        for booking in bookings:
            if not booking.time_slot_id:
                continue
            if not self._date_ranges_overlap(
                    entry.effective_date_start,
                    entry.effective_date_end,
                    booking.booking_date, booking.booking_date):
                continue
            if self._time_ranges_overlap(
                    slot.start_time, slot.end_time,
                    booking.time_slot_id.start_time,
                    booking.time_slot_id.end_time):
                return False
        return True

    @api.model
    def move_suggest(self, entry_id, max_suggestions=3):
        """Propose up to N free room/slot alternatives (drafts only)."""
        self.check_tool_access('move_suggest')
        try:
            entry_id = int(entry_id)
        except (TypeError, ValueError):
            raise UserError(_('Invalid timetable entry id: %r.') % (
                entry_id,))
        try:
            max_suggestions = int(max_suggestions or 3)
        except (TypeError, ValueError):
            max_suggestions = 3
        max_suggestions = max(1, min(max_suggestions, 5))

        entry = self.env['edicai.timetable.entry'].browse(entry_id)
        if not entry.exists():
            raise UserError(_('Timetable entry #%s not found.') % entry_id)
        entry.display_name  # access check under record rules
        if entry.company_id != self.env.company:
            raise UserError(_(
                'Entry "%s" belongs to another institution.')
                % entry.display_name)
        if entry.entry_state == 'cancelled':
            raise UserError(_(
                'Entry "%s" is cancelled; no move is needed.')
                % entry.display_name)

        scope_entries = self.env['edicai.timetable.entry'].search(
            self._scan_domain(
                semester_id=entry.semester_id.id
                if entry.semester_id else None,
                campus_id=entry.campus_id.id
                if entry.campus_id else None,
            ),
        )
        clashes = []
        for other in scope_entries:
            if other.id == entry.id:
                continue
            kinds = self._pair_clash_types(entry, other)
            for kind in kinds:
                clashes.append({
                    'type': kind,
                    'other_entry': self._serialize_entry(other),
                })

        need = entry.course_offering_id.max_enrollment \
            if entry.course_offering_id else 0
        rooms = self.env['edicai.room'].search([
            ('company_id', '=', self.env.company.id),
            ('campus_id', '=', entry.campus_id.id)
            if entry.campus_id else ('campus_id', '!=', False),
            ('capacity', '>=', need or 0),
        ], order='capacity asc')
        rooms = rooms.filtered(lambda r: r.id != entry.room_id.id)
        preferred_rooms = rooms.filtered(
            lambda r: r.room_state == 'available') or rooms
        slots = self.env['edicai.time.slot'].search([
            ('company_id', '=', self.env.company.id),
        ], order='sequence, start_time')
        slots = slots.filtered(lambda s: not s.is_break)
        if entry.campus_id:
            slots = slots.filtered(
                lambda s: not s.campus_id
                or s.campus_id.id == entry.campus_id.id)

        ordered_days = [entry.day_of_week] + [
            day for day in ['0', '1', '2', '3', '4', '5', '6']
            if day != entry.day_of_week
        ]
        suggestions = []
        seen = set()
        # Priority 1: same day + same slot, different room (minimal move).
        # Priority 2: same day + same room is impossible here (room kept
        # would still clash), so try same day other slots, then other days.
        candidates = []
        for day in ordered_days:
            for slot in slots:
                same_time = (
                    day == entry.day_of_week
                    and entry.time_slot_id
                    and slot.id == entry.time_slot_id.id
                )
                for room in preferred_rooms:
                    candidates.append((not same_time, slot, room, day))
        candidates.sort(key=lambda c: (
            c[0],
            0 if c[3] == entry.day_of_week else 1,
            c[1].sequence,
            c[2].capacity,
        ))
        for _not_same, slot, room, day in candidates:
            if len(suggestions) >= max_suggestions:
                break
            key = (day, slot.id, room.id)
            if key in seen:
                continue
            seen.add(key)
            if not self._candidate_is_free(
                    entry, day, slot, room, scope_entries):
                continue
            if day == entry.day_of_week \
                    and entry.time_slot_id \
                    and slot.id == entry.time_slot_id.id:
                reason = _(
                    'Same day and time (%s), different room "%s" '
                    '(capacity %d meets need %d) — no change for '
                    'students or instructor timing.'
                ) % (
                    slot.display_label, room.display_name,
                    room.capacity, need or 0,
                )
            elif day == entry.day_of_week:
                reason = _(
                    'Same day (%s), room "%s" at %s (capacity %d) — '
                    'keeps the teaching day, only the period shifts.'
                ) % (
                    _DAY_LABELS.get(day, ''), room.display_name,
                    slot.display_label, room.capacity,
                )
            else:
                reason = _(
                    'Move to %s, room "%s" at %s (capacity %d) — '
                    'free for room, instructor and section.'
                ) % (
                    _DAY_LABELS.get(day, ''), room.display_name,
                    slot.display_label, room.capacity,
                )
            suggestions.append({
                'type': 'move_draft',
                'entry_id': entry.id,
                'day_of_week': day,
                'day_label': _DAY_LABELS.get(day, ''),
                'time_slot_id': slot.id,
                'time_slot_name': slot.display_label,
                'room_id': room.id,
                'room_name': room.display_name,
                'room_capacity': room.capacity,
                'required_capacity': need or 0,
                'reason': reason,
                'requires_human_approval': True,
            })

        return {
            'entry': self._serialize_entry(entry),
            'required_capacity': need or 0,
            'clashes': clashes,
            'clash_count': len(clashes),
            'suggestions': suggestions,
            'suggestion_count': len(suggestions),
            'requires_human_approval': True,
            'warning': _(
                'DRAFT ONLY — nothing was changed. A scheduler must '
                'review and apply one alternative via the timetable UI; '
                'model constraints will re-validate on save.',
            ),
        }
