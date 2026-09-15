"""
Generate Timetable Wizard — Option A Greedy Heuristic

Automatically generates oacis.timetable.entry records for a
given semester + campus (+ optional program filter) by assigning
free day_of_week / time_slot / room / instructor combinations
without violating the 3-D conflict constraints defined in
oacis.timetable.entry._check_scheduling_conflicts.

Implements preview → edit → generate flow mirroring
oacis.generate.weeks.wizard and oacis.generate.sessions.wizard.
"""
import logging
import math
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Mapping: course slot type -> allowed room types
# ------------------------------------------------------------
_LECTURE_ROOM_TYPES = ['classroom', 'lecture_hall', 'seminar', 'conference']
_LAB_ROOM_TYPES = ['lab', 'computer_lab']
_ALL_TEACHING_ROOM_TYPES = _LECTURE_ROOM_TYPES + _LAB_ROOM_TYPES


def _get_required_sessions(course):
    """Derive required weekly sessions from course contact hours.

    Returns list of dicts: [{'slot_type': 'lecture'|'lab', 'count': int}, ...]
    """
    theory = course.theory_hours or 0.0
    lab = course.lab_hours or 0.0
    tutorial = course.tutorial_hours or 0.0
    total = course.total_contact_hours or 0.0
    ctype = course.course_type or 'theory'

    result = []
    if ctype == 'theory':
        cnt = math.ceil(total) if total > 0 else 1
        result.append({'slot_type': 'lecture', 'count': int(cnt)})
    elif ctype in ('practical',):
        cnt = math.ceil(total) if total > 0 else 1
        result.append({'slot_type': 'lab', 'count': int(cnt)})
    elif ctype in ('theory_practical', 'blended', 'project', 'seminar', 'online'):
        # Split theory+tutorial vs lab
        lec = math.ceil(theory + tutorial) if (theory + tutorial) > 0 else 0
        labc = math.ceil(lab) if lab > 0 else 0
        # Fallback if both zero but total > 0
        if lec == 0 and labc == 0 and total > 0:
            lec = math.ceil(total)
        if lec > 0:
            result.append({'slot_type': 'lecture', 'count': int(lec)})
        if labc > 0:
            result.append({'slot_type': 'lab', 'count': int(labc)})
        if not result:
            result.append({'slot_type': 'lecture', 'count': 1})
    else:
        cnt = math.ceil(total) if total > 0 else 1
        result.append({'slot_type': 'lecture', 'count': int(cnt)})

    # Guard: at least 1 session, max 10 per offering per week
    for r in result:
        r['count'] = max(1, min(r['count'], 10))
    return result


def _room_types_for_slot(slot_type):
    if slot_type == 'lecture':
        return _LECTURE_ROOM_TYPES
    if slot_type == 'lab':
        return _LAB_ROOM_TYPES
    return _ALL_TEACHING_ROOM_TYPES


class OacisGenerateTimetableWizard(models.TransientModel):
    _name = 'oacis.generate.timetable.wizard'
    _description = 'Generate Timetable Wizard (Greedy)'

    semester_id = fields.Many2one(
        comodel_name='oacis.semester',
        string='Semester',
        required=True,
        ondelete='cascade',
        domain="[('company_id', '=', company_id)]",
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus',
        string='Campus',
        required=True,
        ondelete='cascade',
        domain="[('company_id', '=', company_id)]",
    )
    program_id = fields.Many2one(
        comodel_name='oacis.program',
        string='Program (Optional)',
        domain="[('company_id', '=', company_id)]",
        help='Leave empty to include all programs in the semester.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    include_saturday = fields.Boolean(
        string='Include Saturday',
        default=False,
        help='If checked, Saturday is considered for scheduling.',
    )
    include_sunday = fields.Boolean(
        string='Include Sunday',
        default=False,
    )
    skip_existing = fields.Boolean(
        string='Skip Existing Entries',
        default=True,
        help='If True, existing timetable entries for an offering at a '
             'given day/slot are kept and not regenerated.',
    )
    clear_existing = fields.Selection(
        selection=[
            ('keep', 'Keep Existing'),
            ('clear_draft', 'Clear Draft Only'),
            ('clear_all', 'Clear Draft & Confirmed'),
        ],
        string='Clear Existing Before Generate',
        default='keep',
        required=True,
    )
    auto_confirm = fields.Boolean(
        string='Auto-Confirm Generated Entries',
        default=False,
        help='If checked, entries are created as confirmed instead of draft.',
    )
    preview_line_ids = fields.One2many(
        comodel_name='oacis.generate.timetable.line',
        inverse_name='wizard_id',
        string='Preview Lines',
    )
    unscheduled_line_ids = fields.One2many(
        comodel_name='oacis.generate.timetable.unscheduled.line',
        inverse_name='wizard_id',
        string='Unscheduled',
    )
    # Stats
    offering_count = fields.Integer(
        string='Offerings Found',
        compute='_compute_stats',
        store=False,
    )
    required_sessions = fields.Integer(
        string='Required Sessions',
        compute='_compute_stats',
        store=False,
    )
    scheduled_count = fields.Integer(
        string='Scheduled (Preview)',
        compute='_compute_stats',
        store=False,
    )
    unscheduled_count = fields.Integer(
        string='Unscheduled',
        compute='_compute_stats',
        store=False,
    )

    @api.depends('preview_line_ids', 'unscheduled_line_ids')
    def _compute_stats(self):
        for rec in self:
            rec.scheduled_count = len(rec.preview_line_ids)
            rec.unscheduled_count = len(rec.unscheduled_line_ids)
            # required = scheduled + unscheduled (if preview exists)
            # offering_count derived from preview + unscheduled unique offerings
            offering_ids = set(
                rec.preview_line_ids.mapped('course_offering_id').ids
            ) | set(
                rec.unscheduled_line_ids.mapped('course_offering_id').ids
            )
            rec.offering_count = len(offering_ids)
            rec.required_sessions = rec.scheduled_count + rec.unscheduled_count

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------
    def _get_offerings(self):
        self.ensure_one()
        Offering = self.env['oacis.course.offering']
        domain = [
            ('semester_id', '=', self.semester_id.id),
            ('campus_id', '=', self.campus_id.id),
            ('company_id', '=', self.company_id.id),
            ('offering_state', 'in', ['draft', 'open', 'ongoing']),
        ]
        if self.program_id:
            domain.append(('program_id', '=', self.program_id.id))
        return Offering.search(domain, order='max_enrollment desc, course_id asc')

    def _get_time_slots(self):
        self.ensure_one()
        Slot = self.env['oacis.time.slot']
        domain = [
            ('company_id', '=', self.company_id.id),
            ('is_break', '=', False),
        ]
        # campus scoping: slot.campus_id is either False (global) or our campus
        all_slots = Slot.search(domain, order='sequence, start_time')
        # Filter campus compatible
        filtered = all_slots.filtered(
            lambda s: not s.campus_id or s.campus_id.id == self.campus_id.id
        )
        return filtered

    def _get_rooms(self):
        self.ensure_one()
        Room = self.env['oacis.room']
        # campus filtered via floor -> campus, but room has related campus_id
        rooms = Room.search([
            ('campus_id', '=', self.campus_id.id),
            ('room_state', '=', 'available'),
        ], order='capacity asc, name asc')
        return rooms

    def _get_active_days(self):
        self.ensure_one()
        days = ['0', '1', '2', '3', '4']  # Mon-Fri
        if self.include_saturday:
            days.append('5')
        if self.include_sunday:
            days.append('6')
        return days

    def _build_occupancy(self):
        """Build occupancy sets from existing non-cancelled entries + bookings.

        Returns dicts for quick conflict checks.
        """
        self.ensure_one()
        TimetableEntry = self.env['oacis.timetable.entry']
        RoomBooking = self.env['oacis.room.booking']

        # Existing timetable entries for same semester+campus, not cancelled
        # We use semester_id via related field (stored) and campus_id.
        existing = TimetableEntry.search([
            ('semester_id', '=', self.semester_id.id),
            ('campus_id', '=', self.campus_id.id),
            ('entry_state', '!=', 'cancelled'),
        ])
        occupied_room = set()  # (day, slot_id, room_id)
        occupied_instructor = set()  # (day, slot_id, instructor_id)
        occupied_offering = set()  # (offering_id, day, slot_id)
        # For overlap we already filter same semester => same effective range => assume overlap.
        # So any same day+slot is conflict regardless of effective dates for same semester generation.
        for e in existing:
            occupied_room.add((e.day_of_week, e.time_slot_id.id, e.room_id.id))
            occupied_instructor.add((e.day_of_week, e.time_slot_id.id, e.instructor_id.id))
            occupied_offering.add((e.course_offering_id.id, e.day_of_week, e.time_slot_id.id))

        # Room bookings block specific room+day+slot
        bookings = RoomBooking.search([
            ('campus_id', '=', self.campus_id.id),
            ('booking_state', '!=', 'cancelled'),
        ])
        # Only bookings that could overlap semester date range
        # If booking_date within semester range, block it
        sem_start = self.semester_id.date_start
        sem_end = self.semester_id.date_end
        for b in bookings:
            if sem_start and sem_end and b.booking_date:
                if not (sem_start <= b.booking_date <= sem_end):
                    continue
            occupied_room.add((b.day_of_week, b.time_slot_id.id, b.room_id.id))

        return {
            'room': occupied_room,
            'instructor': occupied_instructor,
            'offering': occupied_offering,
            'existing_entries': existing,
        }

    def _instructor_weekly_load(self):
        """Return dict instructor_id -> count of preview+existing entries.

        Used to warn about max_weekly_hours overload.
        Each entry ~ 1 hour (use slot duration if available).
        """
        self.ensure_one()
        load = defaultdict(int)
        # Count existing entries per instructor in this semester
        existing = self.env['oacis.timetable.entry'].search([
            ('semester_id', '=', self.semester_id.id),
            ('campus_id', '=', self.campus_id.id),
            ('entry_state', '!=', 'cancelled'),
        ])
        for e in existing:
            load[e.instructor_id.id] += 1
        for line in self.preview_line_ids:
            if line.instructor_id:
                load[line.instructor_id.id] += 1
        return load

    # --------------------------------------------------------
    # Preview Action (Greedy)
    # --------------------------------------------------------
    def action_preview(self):
        self.ensure_one()
        if not self.semester_id or not self.campus_id:
            raise UserError(_('Semester and Campus are required.'))
        # Validate semester belongs to company
        if self.semester_id.company_id.id != self.company_id.id:
            raise UserError(_('Selected semester does not belong to the chosen institution.'))

        self.preview_line_ids.unlink()
        self.unscheduled_line_ids.unlink()

        offerings = self._get_offerings()
        if not offerings:
            raise UserError(_(
                'No course offerings found for Semester "%s" at Campus "%s" '
                'with state draft/open/ongoing. Create offerings first.'
            ) % (self.semester_id.display_name or self.semester_id.name,
                 self.campus_id.display_name or self.campus_id.name))

        time_slots = self._get_time_slots()
        if not time_slots:
            raise UserError(_('No teaching time slots found for this institution/campus. Configure time slots first.'))

        rooms = self._get_rooms()
        if not rooms:
            raise UserError(_('No available rooms found for campus "%s".') % self.campus_id.display_name)

        active_days = self._get_active_days()
        occupancy = self._build_occupancy()
        occupied_room = set(occupancy['room'])
        occupied_instructor = set(occupancy['instructor'])
        occupied_offering = set(occupancy['offering'])

        # Pre-group rooms by type for faster filtering
        rooms_by_type = defaultdict(list)
        for r in rooms:
            rooms_by_type[r.room_type].append(r)
        # Also all rooms list sorted by capacity
        all_rooms_sorted = sorted(rooms, key=lambda r: (r.capacity, r.name))

        PreviewLine = self.env['oacis.generate.timetable.line']
        UnscheduledLine = self.env['oacis.generate.timetable.unscheduled.line']

        # Track instructor load for overload warnings
        instructor_load = defaultdict(int)
        for e in occupancy['existing_entries']:
            instructor_load[e.instructor_id.id] += 1

        # Sort offerings: lab-heavy + large enrollment first (harder to place)
        def _offering_sort_key(o):
            course = o.course_id
            lab_hours = course.lab_hours or 0
            # Larger enrollment and lab hours first
            return (-o.max_enrollment, -lab_hours, o.course_id.code or '')

        offerings_sorted = sorted(offerings, key=_offering_sort_key)

        # For spread heuristic: track days/slots already used per offering and global slot usage to use all time slots
        offering_days_used = defaultdict(set)
        offering_slots_used = defaultdict(set)  # track which slots each offering has used
        slot_day_usage = defaultdict(int)
        for (d, s_id, _r) in occupied_room:
            slot_day_usage[(d, s_id)] += 1

        # Precompute existing count per offering for skip_existing handling
        existing_per_offering = defaultdict(int)
        for e in occupancy['existing_entries']:
            existing_per_offering[e.course_offering_id.id] += 1

        for offering in offerings_sorted:
            course = offering.course_id
            required_list = _get_required_sessions(course)
            # Adjust required counts if skip_existing and already has entries
            if self.skip_existing:
                total_required = sum(r['count'] for r in required_list)
                existing_cnt = existing_per_offering.get(offering.id, 0)
                if existing_cnt >= total_required:
                    # Already fully scheduled — skip
                    continue
                remaining = total_required - existing_cnt
                # Reduce required_list proportionally
                adjusted = []
                for r in required_list:
                    if remaining <= 0:
                        break
                    take = min(r['count'], remaining)
                    adjusted.append({'slot_type': r['slot_type'], 'count': take})
                    remaining -= take
                required_list = adjusted
                if not required_list:
                    continue
            # Determine instructor candidates
            primary = offering.faculty_member_id
            co_instructors = offering.co_instructor_ids
            # Filter to active members
            candidates = []
            if primary and primary.member_state == 'active':
                candidates.append(primary)
            for ci in co_instructors:
                if ci.member_state == 'active' and ci.id not in [c.id for c in candidates]:
                    candidates.append(ci)
            if not candidates:
                # No valid instructor -> all sessions unscheduled
                for req in required_list:
                    for _i in range(req['count']):
                        UnscheduledLine.create({
                            'wizard_id': self.id,
                            'course_offering_id': offering.id,
                            'reason': _('No active instructor assigned to offering.'),
                            'required_slot_type': req['slot_type'],
                        })
                continue

            for req in required_list:
                slot_type_needed = req['slot_type']
                allowed_room_types = _room_types_for_slot(slot_type_needed)
                # Candidate rooms filtered by type and capacity
                candidate_rooms = [
                    r for r in all_rooms_sorted
                    if r.room_type in allowed_room_types
                    and r.capacity >= offering.max_enrollment
                ]
                # Fallback: if none meet capacity, allow any capacity but warn
                fallback_rooms = []
                if not candidate_rooms:
                    fallback_rooms = [
                        r for r in all_rooms_sorted
                        if r.room_type in allowed_room_types
                    ]
                    # If still none (e.g., no lab rooms), use any room
                    if not fallback_rooms:
                        fallback_rooms = list(all_rooms_sorted)

                for _idx in range(req['count']):
                    assigned = False
                    # Build all (day, slot) combinations and sort by global usage (least used first)
                    # Sort by: least globally used, prefer unused days, prefer unused SLOTS for this offering, then by slot sequence
                    day_slot_pairs = [(d, s) for d in active_days for s in time_slots]
                    day_slot_pairs.sort(key=lambda ds: (
                        slot_day_usage.get((ds[0], ds[1].id), 0),  # least globally used first
                        ds[0] in offering_days_used[offering.id],  # prefer unused days for this offering
                        ds[1].id in offering_slots_used[offering.id],  # prefer unused SLOTS for this offering
                        ds[1].sequence  # then by slot sequence
                    ))

                    for day, slot in day_slot_pairs:
                        if assigned:
                            break
                        # Offering already has entry at this day/slot?
                        if (offering.id, day, slot.id) in occupied_offering:
                            if self.skip_existing:
                                continue
                            else:
                                continue
                        # Try instructors in order
                        for instructor in candidates:
                            # Instructor conflict?
                            if (day, slot.id, instructor.id) in occupied_instructor:
                                continue
                            # Instructor overload check (soft): warn if exceeds max_weekly_hours
                            hours = (slot.duration_minutes or 60) / 60.0
                            current_load = instructor_load.get(instructor.id, 0)
                            max_hours = instructor.max_weekly_hours or 18
                            will_overload = (current_load + hours) > max_hours

                            # Try rooms
                            rooms_to_try = candidate_rooms if candidate_rooms else fallback_rooms
                            rooms_to_try_sorted = sorted(
                                rooms_to_try,
                                key=lambda r: (r.capacity, r.name)
                            )
                            for room in rooms_to_try_sorted:
                                if (day, slot.id, room.id) in occupied_room:
                                    continue
                                # Found feasible assignment
                                warning = ''
                                if not candidate_rooms and fallback_rooms:
                                    if room.capacity < offering.max_enrollment:
                                        warning = _('Room capacity %d < max enrollment %d') % (room.capacity, offering.max_enrollment)
                                if will_overload:
                                    w2 = _('Instructor %s would exceed max %d hrs (current %d + %.1f)') % (
                                        instructor.display_name, max_hours, current_load, hours
                                    )
                                    warning = (warning + '; ' + w2) if warning else w2

                                line_state = 'ok' if not warning else 'warning'

                                PreviewLine.create({
                                    'wizard_id': self.id,
                                    'course_offering_id': offering.id,
                                    'day_of_week': day,
                                    'time_slot_id': slot.id,
                                    'room_id': room.id,
                                    'instructor_id': instructor.id,
                                    'required_slot_type': slot_type_needed,
                                    'warning': warning,
                                    'line_state': line_state,
                                })
                                # Occupy
                                occupied_room.add((day, slot.id, room.id))
                                occupied_instructor.add((day, slot.id, instructor.id))
                                occupied_offering.add((offering.id, day, slot.id))
                                instructor_load[instructor.id] = current_load + hours
                                offering_days_used[offering.id].add(day)
                                offering_slots_used[offering.id].add(slot.id)
                                slot_day_usage[(day, slot.id)] += 1
                                assigned = True
                                break
                            if assigned:
                                break
                        # end instructor loop
                    # end day_slot_pairs loop
                    if not assigned:
                        UnscheduledLine.create({
                            'wizard_id': self.id,
                            'course_offering_id': offering.id,
                            'reason': _('No free room/instructor/slot combination found for %s session.') % slot_type_needed,
                            'required_slot_type': slot_type_needed,
                        })

        _logger.info(
            'Timetable preview: semester=%s campus=%s offerings=%d scheduled=%d unscheduled=%d',
            self.semester_id.name, self.campus_id.name,
            len(offerings_sorted), len(self.preview_line_ids), len(self.unscheduled_line_ids)
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Timetable Preview'),
            'res_model': 'oacis.generate.timetable.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_generate(self):
        self.ensure_one()
        if not self.preview_line_ids and not self.unscheduled_line_ids:
            # Check if preview was run but nothing to schedule (already fully scheduled)
            # Allow generate to report 0 created rather than error
            # But if wizard has never been previewed, offering_count will be 0
            # Distinguish by checking if semester/campus set
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Timetable Generation'),
                    'message': _('No new sessions to schedule — all offerings already have their required entries (skip existing).'),
                    'type': 'info',
                    'sticky': False,
                },
            }

        TimetableEntry = self.env['oacis.timetable.entry']

        # Handle clear_existing
        if self.clear_existing != 'keep':
            domain = [
                ('semester_id', '=', self.semester_id.id),
                ('campus_id', '=', self.campus_id.id),
                ('entry_state', '!=', 'cancelled'),
            ]
            if self.program_id:
                # Filter via offering's program
                domain.append(('course_offering_id.program_id', '=', self.program_id.id))
            if self.clear_existing == 'clear_draft':
                domain.append(('entry_state', '=', 'draft'))
            # clear_all keeps cancelled out already
            existing_to_clear = TimetableEntry.search(domain)
            if existing_to_clear:
                # If skip_existing is True we should not delete entries that are referenced in preview occupancy?
                # For MVP, respect clear_existing explicitly.
                _logger.info('Clearing %d existing entries before generation (mode=%s)', len(existing_to_clear), self.clear_existing)
                existing_to_clear.unlink()

        created_count = 0
        skipped_count = 0
        errors = []

        for line in self.preview_line_ids:
            # Skip if already exists (idempotency when keep mode + skip_existing)
            if self.skip_existing:
                exists = TimetableEntry.search([
                    ('course_offering_id', '=', line.course_offering_id.id),
                    ('day_of_week', '=', line.day_of_week),
                    ('time_slot_id', '=', line.time_slot_id.id),
                    ('entry_state', '!=', 'cancelled'),
                ], limit=1)
                if exists:
                    skipped_count += 1
                    continue

            vals = {
                'course_offering_id': line.course_offering_id.id,
                'day_of_week': line.day_of_week,
                'time_slot_id': line.time_slot_id.id,
                'room_id': line.room_id.id,
                'instructor_id': line.instructor_id.id,
                'entry_state': 'confirmed' if self.auto_confirm else 'draft',
            }
            try:
                with self.env.cr.savepoint():
                    rec = TimetableEntry.create(vals)
                    # If auto_confirm, the create already sets entry_state; but constraints run on create
                    created_count += 1
                    _logger.debug('Created timetable entry %s', rec.display_name)
            except (ValidationError, UserError) as e:
                errors.append('%s: %s' % (line.course_offering_id.display_name or line.course_offering_id.name, str(e)))
                _logger.warning('Failed to create entry for %s: %s', line.course_offering_id.display_name, e)

        # Notification
        msg_parts = [_('%d entries created') % created_count]
        if skipped_count:
            msg_parts.append(_('%d skipped (already exists)') % skipped_count)
        if len(self.unscheduled_line_ids):
            msg_parts.append(_('%d sessions could not be scheduled') % len(self.unscheduled_line_ids))
        if errors:
            msg_parts.append(_('%d errors') % len(errors))

        full_msg = ', '.join(msg_parts) + '.'
        if errors:
            full_msg += '\n' + '\n'.join(errors[:5])
            if len(errors) > 5:
                full_msg += '\n... and %d more' % (len(errors) - 5)
        if self.unscheduled_line_ids:
            # Append unscheduled reasons summary
            unsched_summary = '\n' + _('Unscheduled: ') + ', '.join(
                set(u.course_offering_id.display_name + '(%s)' % u.required_slot_type for u in self.unscheduled_line_ids[:10])
            )
            full_msg += unsched_summary

        notif_type = 'success' if created_count > 0 and not errors else ('warning' if created_count > 0 else 'danger')

        # Post to semester chatter if exists
        try:
            self.semester_id.message_post(body=_('Timetable generation: %s') % full_msg)
        except Exception:
            pass

        if created_count > 0:
            # Return action to show generated entries
            return {
                'type': 'ir.actions.act_window',
                'name': _('Generated Timetable Entries'),
                'res_model': 'oacis.timetable.entry',
                'view_mode': 'list,form',
                'domain': [
                    ('semester_id', '=', self.semester_id.id),
                    ('campus_id', '=', self.campus_id.id),
                ],
                'context': {'search_default_group_by_day_of_week': 1},
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Timetable Generation'),
                'message': full_msg,
                'type': notif_type,
                'sticky': True,
            },
        }

    @api.onchange('semester_id')
    def _onchange_semester(self):
        if self.semester_id and self.semester_id.academic_year_id:
            # Default campus from semester? no, keep as is
            pass

    @api.onchange('company_id')
    def _onchange_company(self):
        if self.company_id:
            self.semester_id = False
            self.campus_id = False
            self.program_id = False


class OacisGenerateTimetableLine(models.TransientModel):
    _name = 'oacis.generate.timetable.line'
    _description = 'Timetable Generation Preview Line'

    wizard_id = fields.Many2one(
        comodel_name='oacis.generate.timetable.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    course_offering_id = fields.Many2one(
        comodel_name='oacis.course.offering',
        string='Course Offering',
        required=True,
        readonly=True,
    )
    course_id = fields.Many2one(
        comodel_name='oacis.course',
        string='Course',
        related='course_offering_id.course_id',
        store=True,
        readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='oacis.semester',
        string='Semester',
        related='course_offering_id.semester_id',
        store=True,
        readonly=True,
    )
    day_of_week = fields.Selection(
        selection=[
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
        ],
        string='Day',
        required=True,
    )
    time_slot_id = fields.Many2one(
        comodel_name='oacis.time.slot',
        string='Time Slot',
        required=True,
    )
    room_id = fields.Many2one(
        comodel_name='oacis.room',
        string='Room',
        required=True,
    )
    instructor_id = fields.Many2one(
        comodel_name='oacis.faculty.member',
        string='Instructor',
        required=True,
    )
    required_slot_type = fields.Selection(
        selection=[
            ('lecture', 'Lecture'),
            ('lab', 'Lab'),
        ],
        string='Slot Type Needed',
        required=True,
        default='lecture',
    )
    warning = fields.Char(
        string='Warning',
        readonly=True,
    )
    line_state = fields.Selection(
        selection=[
            ('ok', 'OK'),
            ('warning', 'Warning'),
        ],
        string='State',
        default='ok',
        required=True,
    )


class OacisGenerateTimetableUnscheduledLine(models.TransientModel):
    _name = 'oacis.generate.timetable.unscheduled.line'
    _description = 'Timetable Unscheduled Line'

    wizard_id = fields.Many2one(
        comodel_name='oacis.generate.timetable.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    course_offering_id = fields.Many2one(
        comodel_name='oacis.course.offering',
        string='Course Offering',
        required=True,
        readonly=True,
    )
    course_id = fields.Many2one(
        comodel_name='oacis.course',
        related='course_offering_id.course_id',
        store=True,
        readonly=True,
    )
    required_slot_type = fields.Selection(
        selection=[
            ('lecture', 'Lecture'),
            ('lab', 'Lab'),
        ],
        string='Slot Type Needed',
        required=True,
    )
    reason = fields.Char(
        string='Reason',
        required=True,
    )
