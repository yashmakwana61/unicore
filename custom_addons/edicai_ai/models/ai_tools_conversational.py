"""Phase 1A — the five allow-listed READ-ONLY conversational tools.

These handlers are the ONLY conversational surface. They are invoked
exclusively through the central registry path
(``edicai.ai.tool.registry.execute_tool``) — group gate, company scope
injection, per-tool rate limit and durable audit remain those of the
registry. Every handler:

* performs only ``search`` / ``read`` / ``browse`` under the calling
  user's own access rights (no ``sudo``, ever);
* reuses EXISTING business tools where available instead of duplicating
  business logic:

    - fees.fee_status      → edicai.fee.copilot.dues_summary
    - timetable.clash_check→ timetable.ai.copilot.clash_scan
    - admission.program_search
                           → edicai.admission.ai.tools.run_tool(
                                 'program_search', ...)
  and adds the smallest safe read-only adapters where a
  student-scoped summary does not exist yet (attendance, grading),
  reading authoritative stored fields only;

* never creates, writes, unlinks, sends or transitions anything;
* returns small structured dicts — no exception payloads, no raw SQL,
  no internal identifiers beyond display names and already-readable
  record ids (citations).
"""

import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: Max rows returned per composed answer (bounded outputs).
MAX_CANDIDATES = 5
MAX_ATTENDANCE_RECORDS = 400

# Error codes in lieu of exceptions: the orchestrator maps these to the
# Phase 0 safe error taxonomy.
ERR_TOOL_UNAVAILABLE = 'TOOL_UNAVAILABLE'
ERR_RECORD_NOT_FOUND = 'RECORD_NOT_FOUND'

# Shared display labels for the grounding/citation layer.
LABEL_ATTENDANCE = 'Attendance Report'
LABEL_TIMETABLE = 'Timetable Clashes'
LABEL_GRADES = 'Grade Summary'
LABEL_PROGRAMS = 'Admission Programs'
LABEL_FEES = 'Fee Status'
LABEL_FEES_SUMMARY = 'Outstanding Fees (all students)'
LABEL_ATTENDANCE_SUMMARY = 'Attendance Shortage (all students)'


def _valid_search_hint(value, max_len=120):
    """Closed scalar grammar for ORM ilike values (no wildcard widening)."""
    if not isinstance(value, str) or not value.strip() \
            or len(value) > max_len:
        return False
    return all(char.isalnum() or char.isspace() or char in '.&/()-'
               for char in value)


class EdicaiAIConversationalTools(models.AbstractModel):
    """Handlers for the five Phase 1A conversational read-only tools."""

    _name = 'edicai.ai.conversational.tools'
    _description = 'AI Conversational Read-Only Tools (Phase 1A)'

    # ------------------------------------------------------------------
    # Shared scope helpers (same semantics as edicai.fee.copilot)
    # ------------------------------------------------------------------

    @api.model
    def _staff_groups(self):
        return (
            'edicai_base.group_edicai_admin',
            'edicai_base.group_edicai_finance',
            'edicai_base.group_edicai_manager',
            'edicai_base.group_edicai_registrar',
            'edicai_base.group_edicai_staff',
            'edicai_base.group_edicai_faculty',
        )

    @api.model
    def _is_restricted_student(self):
        """True when the caller is a student user without staff groups."""
        user = self.env.user
        try:
            has_student = user.has_group('edicai_base.group_edicai_student')
        except Exception:
            has_student = False
        if not has_student:
            return False
        try:
            return not any(user.has_group(group)
                           for group in self._staff_groups())
        except Exception:
            return False

    @api.model
    def _faculty_finance_denied(self):
        """Extra least-privilege guard for faculty cohort fee reads.

        Odoo ACLs/record rules still decide access. This application policy
        narrows the conversational cohort surface further: faculty without
        an explicit finance/manager/admin role cannot enumerate fee data.
        """
        user = self.env.user
        try:
            if not user.has_group('edicai_base.group_edicai_faculty'):
                return False
            return not any(user.has_group(xmlid) for xmlid in (
                'edicai_base.group_edicai_finance',
                'edicai_base.group_edicai_manager',
                'edicai_base.group_edicai_admin',
            ))
        except Exception:
            return True

    @api.model
    def _own_student_ids(self):
        """Students linked to the current login via the billing partner."""
        return self.env['edicai.student'].search([
            ('partner_id.user_ids', 'in', [self.env.user.id]),
        ])

    @api.model
    def _resolve_target_student(self, params):
        """Resolve the student a read tool should answer about.

        :returns: ``(status, student, candidates)`` where status is one
            of ``'ok'`` / ``'clarify'`` / ``'not_found'`` /
            ``'unavailable'``; candidates is a bounded list of display
            names for the clarify case.
        """
        if 'edicai.student' not in self.env:
            return 'unavailable', False, []
        name = str((params or {}).get('student_name') or '').strip()
        if self._is_restricted_student():
            own = self._own_student_ids()
            if not own:
                return 'not_found', False, []
            if len(own) == 1:
                return 'ok', own, []
            # Several linked students: bounded clarification.
            names = ', '.join(own.mapped('display_name')[:MAX_CANDIDATES])
            return 'clarify', own, [names]
        # Staff / faculty / manager: an EXPLICIT name is required.
        if not name:
            return 'clarify', False, []
        matches = self.env['edicai.student'].search([
            ('company_id', '=', self.env.company.id),
            # ``name`` holds only the given name; the stored
            # ``display_name`` is the full 'name [middle] last_name'.
            ('display_name', 'ilike', name),
        ], limit=MAX_CANDIDATES + 1)
        if not matches:
            return 'not_found', False, []
        if len(matches) > 1:
            return 'clarify', False, matches.mapped('display_name')
        return 'ok', matches, []

    def _ambiguity_reply(self, label, candidates):
        """Bounded clarification payload (never silently selects one)."""
        names = ', '.join((candidates or [])[:MAX_CANDIDATES])
        return {
            'label': label,
            'clarify': names,
        }

    def _unavailable(self, model_name):
        return {
            'error_code': ERR_TOOL_UNAVAILABLE,
            'detail': model_name,
        }

    def _not_found(self):
        return {'error_code': ERR_RECORD_NOT_FOUND}

    # ------------------------------------------------------------------
    # Tool: attendance.shortage_report
    # ------------------------------------------------------------------

    @api.model
    def tool_attendance_report(self, params):
        """Authorized per-course attendance summary for one student."""
        if 'edicai.attendance.record' not in self.env:
            return self._unavailable('edicai.attendance.record')
        Record = self.env['edicai.attendance.record']
        status, student, candidates = self._resolve_target_student(params)
        if status == 'unavailable':
            return self._unavailable('edicai.student')
        if status == 'clarify':
            return self._ambiguity_reply(LABEL_ATTENDANCE, candidates)
        if status == 'not_found':
            return self._not_found()
        # NOTE: cumulative stats are STORED computes, monotonic in
        # creation order — each record's stored values were computed at
        # its own creation and are NOT re-triggered when later records
        # appear. The last-CREATED record therefore always holds the
        # fullest (self-consistent) view for the student+offering pair,
        # while session_date ordering can surface a stale one.
        records = Record.search([
            ('company_id', '=', self.env.company.id),
            ('student_id', '=', student.id),
        ], order='id desc', limit=MAX_ATTENDANCE_RECORDS)
        latest_by_offering = {}
        for rec in records:
            offering_id = rec.course_offering_id.id or 0
            if offering_id in latest_by_offering:
                continue
            try:
                percentage = rec.cumulative_attendance_percentage or 0.0
            except Exception:
                percentage = 0.0
            course_name = False
            try:
                course_name = (
                    rec.course_id.display_name
                    or rec.course_offering_id.display_name
                    or False
                )
            except Exception:
                course_name = False
            latest_by_offering[offering_id] = {
                'course_name': course_name or 'Course',
                'percentage': round(percentage, 1),
                'sessions_held': rec.total_sessions_held,
                'sessions_present': rec.sessions_present,
                'sessions_absent': rec.sessions_absent,
                'shortage_alert': bool(rec.shortage_alert),
            }
        courses = sorted(
            latest_by_offering.values(),
            key=lambda row: row['course_name'] or '',
        )
        overall = False
        try:
            overall = student.attendance_percentage
        except Exception:
            overall = False
        return {
            'label': LABEL_ATTENDANCE,
            'data': {
                'student': student.display_name,
                'overall_percentage': round(overall, 1) if overall is not None else False,
                'shortage': any(c['shortage_alert'] for c in courses),
                'courses': courses,
                'empty': not courses,
            },
        }

    # ------------------------------------------------------------------
    # Tool: timetable.clash_check
    # ------------------------------------------------------------------

    @api.model
    def tool_clash_check(self, params):
        """Company-scoped timetable clash scan for one entity scope."""
        if 'timetable.ai.copilot' not in self.env:
            return self._unavailable('timetable.ai.copilot')
        Copilot = self.env['timetable.ai.copilot']
        if 'edicai.semester' not in self.env:
            return self._unavailable('edicai.semester')
        Semester = self.env['edicai.semester']
        term = str((params or {}).get('semester_term') or '').strip()
        semester = False
        if term:
            matches = Semester.search([
                ('company_id', '=', self.env.company.id),
                '|',
                ('name', 'ilike', 'semester %s' % term),
                ('code', '=ilike', 'semester %s' % term),
            ], limit=MAX_CANDIDATES + 1)
            if not matches:
                # Fallback: match by code fragment (e.g. "S1").
                matches = Semester.search([
                    ('company_id', '=', self.env.company.id),
                    ('code', '=ilike', 'S%s' % term),
                ], limit=MAX_CANDIDATES + 1)
            if not matches:
                return self._not_found()
            if len(matches) > 1:
                return self._ambiguity_reply(
                    LABEL_TIMETABLE, matches.mapped('display_name'))
            semester = matches
        result = Copilot.clash_scan(
            semester_id=semester.id if semester else None, limit=25)
        reasons = [pair.get('reason') for pair in result.get('pairs', [])]
        return {
            'label': LABEL_TIMETABLE,
            'data': {
                'semester': semester.display_name if semester else False,
                'scanned_entries': result.get('scanned_entries', 0),
                'clash_count': result.get('clash_count', 0),
                'clashes': reasons[:MAX_CANDIDATES],
                'truncated': bool(result.get('truncated')),
                'empty': result.get('clash_count', 0) == 0,
            },
        }

    @api.model
    def tool_timetable_view(self, params):
        """Read scheduled entries for a date, separate from clash scans."""
        if 'timetable.ai.copilot' not in self.env:
            return self._unavailable('timetable.ai.copilot')
        result = self.env['timetable.ai.copilot'].view_schedule(
            schedule_date=(params or {}).get('schedule_date') or 'today',
            limit=(params or {}).get('limit') or 50)
        return {'label': 'Timetable', 'data': result}

    # ------------------------------------------------------------------
    # Tool: grading.grade_summary
    # ------------------------------------------------------------------

    @api.model
    def tool_grade_summary(self, params):
        """Authorized academic summary for one student."""
        if 'edicai.semester.result' not in self.env:
            return self._unavailable('edicai.semester.result')
        Result = self.env['edicai.semester.result']
        status, student, candidates = self._resolve_target_student(params)
        if status == 'unavailable':
            return self._unavailable('edicai.student')
        if status == 'clarify':
            return self._ambiguity_reply(LABEL_GRADES, candidates)
        if status == 'not_found':
            return self._not_found()
        results = Result.search([
            ('company_id', '=', self.env.company.id),
            ('student_id', '=', student.id),
            ('is_published', '=', True),
        ])
        semesters = []
        for res in results:
            try:
                gpa = res.semester_gpa
            except Exception:
                gpa = False
            semesters.append({
                'semester': res.semester_id.display_name if res.semester_id else '—',
                'gpa': gpa,
                'credits_attempted': res.credits_attempted,
                'credits_earned': res.credits_earned,
                'result_status': res.result_status,
            })
        cgpa = False
        average = False
        try:
            cgpa = student.cgpa
        except Exception:
            cgpa = False
        try:
            average = student.average_percentage
        except Exception:
            average = False
        return {
            'label': LABEL_GRADES,
            'data': {
                'student': student.display_name,
                'cgpa': cgpa,
                'average_percentage': average,
                'semesters': semesters,
                'empty': not semesters and not cgpa,
            },
        }

    # ------------------------------------------------------------------
    # Tool: admission.program_search
    # ------------------------------------------------------------------

    @api.model
    def tool_program_search(self, params):
        """Active admission programs (delegated existing tool)."""
        if 'edicai.admission.ai.tools' not in self.env:
            return self._unavailable('edicai.admission.ai.tools')
        Admission = self.env['edicai.admission.ai.tools']
        level = params.get('program_level') or None
        query = params.get('program_query') or None
        campus = params.get('campus') or None
        limit = params.get('limit') or 10
        if query and not _valid_search_hint(query, 60):
            return {'error_code': 'FILTER_INVALID'}
        if campus and not _valid_search_hint(campus, 120):
            return {'error_code': 'FILTER_INVALID'}
        # Keep the delegated admission tool authoritative for company and
        # campus matching. A filter is passed through, never discarded.
        result = Admission.run_tool(
            'program_search', level=level, campus=campus,
            query=query, limit=min(max(int(limit), 1), 25))
        if 'clarify' in result:
            return {'label': LABEL_PROGRAMS, 'clarify': result['clarify']}
        programs = [
            {
                'name': row.get('name'),
                'code': row.get('code'),
                'level': row.get('level'),
                'campuses': row.get('campuses') or [],
                'tuition_per_semester': row.get('tuition_per_semester'),
                'entry_qualification': row.get('entry_qualification'),
            }
            for row in (result.get('programs') or [])
        ]
        requested_limit = min(max(int(limit), 1), 25)
        return {
            'label': LABEL_PROGRAMS,
            'data': {
                'programs': programs,
                'empty': not programs,
                'filters': {
                    'program': query or False,
                    'level': level or False,
                    'campus': campus or False,
                },
                'total_count': result.get('total_count', len(programs)),
                'possibly_truncated': bool(result.get('truncated')),
                'limit': requested_limit,
            },
        }

    @api.model
    def tool_applicant_list(self, params):
        """Company/record-rule scoped applicant collection read.

        Applicant/program/campus values are resolved through current ORM
        records. A vague stage is clarified; no filter is ignored.
        """
        params = params or {}
        if 'edicai.admission.applicant' not in self.env:
            return self._unavailable('edicai.admission.applicant')
        Applicant = self.env['edicai.admission.applicant']
        domain = [('company_id', '=', self.env.company.id)]
        state = params.get('state') or False
        if state:
            choices = dict(Applicant._fields['state'].selection)
            if state not in choices:
                return {
                    'clarify': [],
                    'clarify_message': (
                        '“Pending” is not a single application stage. '
                        'Which stage do you mean?'),
                }
            domain.append(('state', '=', state))
        program_query = str(params.get('program_query') or '').strip()
        if program_query:
            if not _valid_search_hint(program_query, 60):
                return {'error_code': 'FILTER_INVALID'}
            Program = self.env['edicai.program']
            programs = Program.search([
                ('company_id', '=', self.env.company.id),
                '|', ('name', 'ilike', program_query),
                     ('code', '=ilike', program_query),
            ], limit=6)
            if not programs:
                return {'label': 'Admission Applicants', 'data': {
                    'rows': [], 'total_count': 0, 'shown': 0,
                    'truncated': False, 'empty': True,
                    'filters': {'program': program_query},
                }}
            if len(programs) > 1:
                return {'clarify': programs.mapped('display_name')[:5]}
            domain.append(('program_id', '=', programs.id))
        campus_hint = str(params.get('campus') or '').strip()
        if campus_hint:
            if not _valid_search_hint(campus_hint, 120):
                return {'error_code': 'FILTER_INVALID'}
            campuses = self.env['edicai.campus'].search([
                ('company_id', '=', self.env.company.id),
                '|', ('name', 'ilike', campus_hint),
                     ('code', '=ilike', campus_hint),
            ], limit=6)
            if not campuses:
                return {'label': 'Admission Applicants', 'data': {
                    'rows': [], 'total_count': 0, 'shown': 0,
                    'truncated': False, 'empty': True,
                    'filters': {'campus': campus_hint},
                }}
            if len(campuses) > 1:
                return {'clarify': campuses.mapped('display_name')[:5]}
            domain.append(('campus_id', '=', campuses.id))

        no_followup = bool(params.get('no_followup'))
        if no_followup:
            # Delegate the established workflow definition: open-stage,
            # current-company applicants with no open mail.activity.
            if 'edicai.ai.pending.workflow' not in self.env:
                return self._unavailable('edicai.ai.pending.workflow')
            discovered = self.env['edicai.ai.pending.workflow'] \
                ._discover_candidates(self.env.company)
            records = Applicant.browse(
                [record.id for record in discovered]).filtered_domain(domain)
            total = len(records)
            records = records[:min(max(int(params.get('limit') or 10), 1), 100)]
        else:
            total = Applicant.search_count(domain)
            limit = min(max(int(params.get('limit') or 10), 1), 100)
            records = Applicant.search(domain, order='id desc', limit=limit)
        rows = [{
            'id': record.id,
            'name': record.display_name,
            'application_number': record.application_number,
            'state': record.state,
            'program': record.program_id.display_name,
            'campus': record.campus_id.display_name,
        } for record in records]
        return {'label': 'Admission Applicants', 'data': {
            'rows': rows, 'total_count': total, 'shown': len(rows),
            'truncated': total > len(rows), 'empty': not total,
            'filters': {'state': state or False,
                        'program': program_query or False,
                        'campus': campus_hint or False,
                        'no_followup': no_followup},
        }}

    @api.model
    def tool_followup_list(self, params):
        """Read pending applicant activities through current ORM rules."""
        params = params or {}
        if 'edicai.admission.applicant' not in self.env:
            return self._unavailable('edicai.admission.applicant')
        if 'mail.activity' not in self.env:
            return self._unavailable('mail.activity')
        Applicant = self.env['edicai.admission.applicant']
        applicants = Applicant.search([
            ('company_id', '=', self.env.company.id),
        ], order='id desc', limit=5001)
        if len(applicants) > 5000:
            return {'error_code': 'QUERY_TOO_BROAD'}
        if not applicants:
            return {'label': 'Admission Follow-ups', 'data': {
                'rows': [], 'total_count': 0, 'shown': 0,
                'truncated': False, 'empty': True,
            }}
        today = fields.Date.context_today(self)
        date_filter = params.get('date_filter') or 'all'
        domain = [
            ('res_model', '=', 'edicai.admission.applicant'),
            ('res_id', 'in', applicants.ids),
        ]
        if date_filter == 'overdue':
            domain.append(('date_deadline', '<', today))
        elif date_filter == 'today':
            domain.append(('date_deadline', '=', today))
        elif date_filter == 'yesterday':
            domain.append(('date_deadline', '=', today - timedelta(days=1)))
        elif date_filter != 'all':
            return {'error_code': 'FILTER_INVALID'}
        Activity = self.env['mail.activity']
        total = Activity.search_count(domain)
        limit = min(max(int(params.get('limit') or 10), 1), 100)
        activities = Activity.search(
            domain, order='date_deadline, id', limit=limit)
        by_id = {applicant.id: applicant for applicant in applicants}
        rows = []
        for activity in activities:
            applicant = by_id.get(activity.res_id)
            if not applicant:
                continue
            rows.append({
                'applicant': applicant.display_name,
                'application_number': applicant.application_number,
                'summary': activity.summary or '',
                'date_deadline': fields.Date.to_string(
                    activity.date_deadline) if activity.date_deadline else '',
                'assigned_to': activity.user_id.display_name
                if activity.user_id else '',
            })
        return {'label': 'Admission Follow-ups', 'data': {
            'rows': rows, 'total_count': total, 'shown': len(rows),
            'truncated': total > len(rows), 'empty': not total,
            'date_filter': date_filter,
        }}

    @api.model
    def tool_grievance_summary(self, params):
        """Grounded grievance counts by repository state/category."""
        if 'edicai.grievance.request' not in self.env:
            return self._unavailable('edicai.grievance.request')
        Grievance = self.env['edicai.grievance.request']
        domain = [('company_id', '=', self.env.company.id)]
        if (params or {}).get('open_only'):
            domain.append(('state', 'in', [
                'new', 'in_progress', 'escalated']))
        total = Grievance.search_count(domain)
        records = Grievance.search(domain, order='id desc', limit=5001)
        if len(records) > 5000:
            return {'error_code': 'QUERY_TOO_BROAD'}
        by_state = {}
        by_category = {}
        for record in records:
            state = record.state or 'unknown'
            category = record.category_id.display_name or 'Uncategorized'
            by_state[state] = by_state.get(state, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1
        return {'label': 'Grievance Summary', 'data': {
            'total_count': total, 'by_state': by_state,
            'by_category': by_category, 'empty': not total,
        }}

    # ------------------------------------------------------------------
    # Tool: fees.fee_status
    # ------------------------------------------------------------------

    @api.model
    def tool_fee_status(self, params):
        """Authorized fee/payment status (delegated existing tool)."""
        if 'edicai.fee.copilot' not in self.env:
            return self._unavailable('edicai.fee.copilot')
        Copilot = self.env['edicai.fee.copilot']
        status, student, candidates = self._resolve_target_student(params)
        if status == 'unavailable':
            return self._unavailable('edicai.student')
        if status == 'clarify':
            return self._ambiguity_reply(LABEL_FEES, candidates)
        if status == 'not_found':
            return self._not_found()
        result = Copilot.dues_summary(
            student_id=student.id if student else False)
        semesters = result.get('semesters') or []
        currency = result.get('currency') or False
        return {
            'label': LABEL_FEES,
            'data': {
                'student_id': student.id if student else False,
                'student': student.display_name if student else False,
                'currency': currency,
                'grand_outstanding': result.get('grand_outstanding', 0.0),
                'semesters': [
                    {
                        'semester_name': b.get('semester_name'),
                        'amount_outstanding': b.get('amount_outstanding'),
                        'open_count': b.get('open_count'),
                        'overdue_count': b.get('overdue_count'),
                    }
                    for b in semesters
                ],
                # 'empty' = nothing billable at all. A zero grand
                # outstanding WITH semesters is a real grounded answer
                # ("no outstanding fees"), not empty data.
                'empty': not semesters,
            },
        }


    # ------------------------------------------------------------------
    # Tool: fees.fee_summary (AGGREGATE — counts and totals)
    # ------------------------------------------------------------------

    def tool_fee_summary(self, params):
        """Institution-wide outstanding-fee aggregate.

        THIN WRAPPER over the Phase G1 generic aggregate
        (``entity.aggregate``) — the migration pattern from the Phase
        G plan: static cohort tools stop growing custom code and
        delegate to the generic layer. The reply shape is byte-for-byte
        compatible with the Phase 13 implementation (the orchestrator
        composer and all tests keep working unchanged).

        Scope: policy grants + the caller's record rules via the
        generic layer (no sudo). A restricted portal student only ever
        sees their own invoices.
        """
        if 'edicai.fee.invoice' not in self.env:
            return self._unavailable('edicai.fee.invoice')
        if self._faculty_finance_denied():
            return {'error_code': 'AUTHORIZATION_DENIED'}
        Copilot = self.env['edicai.fee.copilot']
        restricted = (
            Copilot._is_restricted_student()
            if 'edicai.fee.copilot' in self.env else False)
        entity_tools = self.env['edicai.ai.entity.tools']
        base_filters = [
            ['amount_outstanding', 'gt', 0.0],
            ['invoice_state', 'ne', 'cancelled'],
        ]
        overdue_only = bool((params or {}).get('overdue_only'))
        try:
            output_limit = min(max(int((params or {}).get('limit') or 10), 1), 50)
        except (TypeError, ValueError):
            output_limit = 10
        if overdue_only:
            base_filters = [
                ['amount_outstanding', 'gt', 0.0],
                ['invoice_state', 'eq', 'overdue'],
            ]
        agg = entity_tools.aggregate_for_policy(
            'edicai.fee.invoice',
            filters=base_filters,
            group_by=['student_id'],
            measures={'amount_outstanding': 'sum'})
        # is_overdue is a NON-stored compute and can never appear in a
        # SQL aggregate; the stored state machine carries the same
        # meaning (invoice_state = 'overdue').
        overdue = entity_tools.aggregate_for_policy(
            'edicai.fee.invoice', filters=base_filters if overdue_only else
            base_filters[:1] + [['invoice_state', 'eq', 'overdue']],
            group_by=['student_id'])

        overdue_by_student = {
            row.get('student_id'): int(row.get('__count') or 0)
            for row in (overdue.get('rows') or [])
        }
        top = []
        for row in (agg.get('rows') or []):
            student_label = row.get('student_id')
            top.append({
                'student': student_label,
                'outstanding': float(
                    row.get('amount_outstanding:sum') or 0.0),
                'invoice_count': int(row.get('__count') or 0),
                'overdue_count': int(
                    overdue_by_student.get(student_label) or 0),
            })
        top.sort(key=lambda r: (-r['outstanding'], r['student'] or ''))
        currency = False
        if top:
            invoice = self.env['edicai.fee.invoice'].search(
                [('amount_outstanding', '>', 0.0),
                 ('invoice_state', '!=', 'cancelled')], limit=1)
            currency = invoice.currency_id.name if invoice else False
        students = len(top)
        return {
            'label': LABEL_FEES_SUMMARY,
            'data': {
                'students_with_outstanding': students,
                'total_outstanding': sum(
                    row['outstanding'] for row in top),
                'currency': currency,
                'overdue_students': len(overdue_by_student),
                'scope': 'own' if restricted else 'company',
                'top_students': top[:output_limit],
                'overdue_only': overdue_only,
                'empty': not students,
            },
        }

    # ------------------------------------------------------------------
    # Tool: attendance.shortage_summary (AGGREGATE — counts)
    # ------------------------------------------------------------------

    def tool_attendance_summary(self, params):
        """Institution-wide attendance-shortage aggregate.

        Answers "how many students are below the attendance policy?".
        """
        if 'attendance.ai.copilot' not in self.env:
            return self._unavailable('attendance.ai.copilot')
        threshold = (params or {}).get('threshold')
        try:
            output_limit = min(max(int((params or {}).get('limit') or 10), 1), 50)
        except (TypeError, ValueError):
            output_limit = 10
        if threshold not in (None, False, ''):
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                return {'error_code': 'FILTER_INVALID'}
            if not 0 < threshold <= 80:
                return {'error_code': 'FILTER_UNSUPPORTED'}
        summary = self.env['attendance.ai.copilot'].shortage_summary(
            include_warning=True, limit=output_limit, threshold=threshold)
        return {
            'label': LABEL_ATTENDANCE_SUMMARY,
            'data': {
                'students_short': summary.get('students_short', 0),
                'shortage_rows': summary.get('shortage_rows', 0),
                'scope': summary.get('scope', 'company'),
                'threshold': threshold,
                'truncated': bool(summary.get('truncated')),
                'worst_students': [
                    {
                        'student': row.get('student'),
                        'percentage': row.get('percentage', 0.0),
                        'offering': row.get('offering'),
                        'min_required': row.get('min_required'),
                        'gap_points': row.get('gap_points'),
                    }
                    for row in (summary.get('worst_students') or [])
                ],
                'empty': not summary.get('students_short'),
            },
        }


# ---------------------------------------------------------------------------
# Self-registration (restart-resilient)
# ---------------------------------------------------------------------------
#
# TOOL_REGISTRY is a process-local dict. Data-file function-tag
# registrations only execute on fresh module INSTALLS (the existing
# Ask-Data registrations in data/ai_registry_data.xml inherit that
# behaviour — a documented Phase 0 gap), so they are absent after a
# restart. The five Phase 1A conversational tools are therefore
# registered IN PYTHON at module load: present in the allow-list on
# every process start, no upgrade required. Re-registering is
# idempotent (overwrites the spec dict).
#
# Group gate, company forcing, rate limit, durable audit: unchanged —
# every execution still goes through edicai.ai.tool.registry
# .execute_tool.

_CONVERSATIONAL_TOOL_NAMES = (
    'attendance.shortage_report',
    'timetable.clash_check',
    'timetable.view',
    'grading.grade_summary',
    'admission.program_search',
    'admission.applicant_list',
    'admission.followup_list',
    'grievance.summary',
    'fees.fee_status',
    # Aggregate (cohort) tools — "how many students ...".
    'fees.fee_summary',
    'attendance.shortage_summary',
)

_CONVERSATIONAL_TOOL_METHODS = {
    'attendance.shortage_report': 'tool_attendance_report',
    'timetable.clash_check': 'tool_clash_check',
    'timetable.view': 'tool_timetable_view',
    'grading.grade_summary': 'tool_grade_summary',
    'admission.program_search': 'tool_program_search',
    'admission.applicant_list': 'tool_applicant_list',
    'admission.followup_list': 'tool_followup_list',
    'grievance.summary': 'tool_grievance_summary',
    'fees.fee_status': 'tool_fee_status',
    'fees.fee_summary': 'tool_fee_summary',
    'attendance.shortage_summary': 'tool_attendance_summary',
}


def _register_phase1a_tools():
    try:
        from odoo.addons.edicai_ai.models.ai_tool_registry import (
            register_tool,
        )
        for _tool_name in _CONVERSATIONAL_TOOL_NAMES:
            register_tool({
                'name': _tool_name,
                'kind': 'tool',
                'description': (
                    'Phase 1A conversational read-only tool '
                    '(%s).' % _tool_name.replace('.', ' ')),
                'model': 'edicai.ai.conversational.tools',
                'method': _CONVERSATIONAL_TOOL_METHODS[_tool_name],
                'allowed_groups': ['edicai_ai.group_edicai_ai_user'],
                'rate_limit_per_hour': 120,
                'risk_level': 'READ_ONLY',
                'phase': '1A',
            })
    except Exception:
        _logger.exception(
            'Phase 1A tools: registration failed (registry stays '
            'without the conversational tools; the orchestrator '
            'rejects them safely).')


_register_phase1a_tools()
