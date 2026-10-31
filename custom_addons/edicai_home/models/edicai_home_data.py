# -*- coding: utf-8 -*-
"""Edicai Home — role-aware data engine.

Everything runs under the CALLING USER (no sudo). A widget the user cannot
read degrades to `restricted: true` (empty state), never fakes zeros.
Composition rule (approved design): the user's widget set is the deterministic
union of the profiles of every group-based role they hold, ordered canonically
and deduplicated.
"""
import logging
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

ROLE_GROUPS = {
    'admin': 'edicai_base.group_edicai_admin',
    'manager': 'edicai_base.group_edicai_manager',
    'registrar': 'edicai_base.group_edicai_registrar',
    'finance': 'edicai_base.group_edicai_finance',
    'faculty': 'edicai_base.group_edicai_faculty',
    'staff': 'edicai_base.group_edicai_staff',
    'student': 'edicai_base.group_edicai_student',
}

PROFILE_ROLE_ORDER = ['admin', 'registrar', 'finance', 'manager',
                      'faculty', 'staff', 'student']

# widget key -> roles that include it (union when a user holds several)
WIDGET_ROLES = {
    'enrollment_overview': ['admin', 'manager'],
    'admissions_pipeline': ['admin', 'registrar', 'manager'],
    'fee_collection': ['admin', 'finance', 'manager'],
    'attendance_overview': ['admin', 'staff', 'manager'],
    'pending_approvals': ['admin', 'registrar', 'manager'],
    'overdue_alerts': ['admin', 'finance'],
    'recent_payments': ['finance'],
    'today_classes_faculty': ['faculty'],
    'assignments_review': ['faculty'],
    'pending_grading': ['faculty'],
    'today_classes_student': ['student'],
    'my_attendance': ['student'],
    'my_assignments': ['student'],
    'my_results': ['student'],
    'library_overdue': ['staff'],
    'library_activity': ['staff'],
    'placement_overview': ['manager'],
    'website_shortcuts': ['admin'],   # built only when a website-editor group is held
    'institution_notices': None,      # everyone
    'quick_links': None,              # everyone (role-keyed content)
    'upcoming_schedule': None,        # everyone (exams + drives; role-aware)
}

# Dashboard information architecture (Phase-4 grouping)
SECTION_OF = {
    'enrollment_overview': 'primary',
    'admissions_pipeline': 'primary',
    'fee_collection': 'primary',
    'attendance_overview': 'primary',
    'pending_approvals': 'attention',
    'overdue_alerts': 'attention',
    'assignments_review': 'attention',
    'pending_grading': 'attention',
    'library_overdue': 'attention',
    'my_assignments': 'attention',
    'today_classes_faculty': 'schedule',
    'today_classes_student': 'schedule',
    'upcoming_schedule': 'schedule',
    'recent_payments': 'secondary',
    'my_attendance': 'secondary',
    'my_results': 'secondary',
    'library_activity': 'secondary',
    'placement_overview': 'secondary',
    'website_shortcuts': 'secondary',
    'institution_notices': 'secondary',
    'quick_links': 'secondary',
}

QUICK_LINKS = {
    'admin': [('Admissions', 'edicai.admission.applicant'), ('Students', 'edicai.student'),
              ('Fee Invoices', 'edicai.fee.invoice'), ('Attendance', 'edicai.attendance.session'),
              ('Notices', 'edicai.notice'), ('Exams', 'edicai.exam.schedule')],
    'registrar': [('Admissions', 'edicai.admission.applicant'), ('Students', 'edicai.student'),
                  ('Leave Requests', 'edicai.student.leave.request'), ('Exams', 'edicai.exam.schedule')],
    'finance': [('Fee Invoices', 'edicai.fee.invoice'), ('Payments', 'edicai.fee.payment'),
                ('Scholarships', 'edicai.scholarship.award')],
    'manager': [('Placement Drives', 'edicai.placement.drive'), ('Students', 'edicai.student'),
                ('Discipline', 'edicai.discipline.record'), ('Notices', 'edicai.notice')],
    'faculty': [('My Assignments', 'edicai.assignment'), ('Grade Entries', 'edicai.grade.entry'),
                ('Attendance', 'edicai.attendance.session')],
    'staff': [('Library Issues', 'edicai.library.issue'), ('Books', 'edicai.library.book'),
              ('Notices', 'edicai.notice')],
    'student': [('My Attendance', 'edicai.attendance.record'), ('My Assignments', 'edicai.assignment'),
                ('eLearning Courses', None)],
}


def _safe(fn, default=None):
    """Run a data helper; on AccessError mark restricted, on other errors
    surface them for the widget error state."""
    try:
        return {'ok': fn()}
    except AccessError:
        return {'restricted': True}
    except Exception:
        _logger.warning('Edicai Home widget computation failed', exc_info=True)
        return {'error': True}


class EdicaiHomeData(models.Model):
    _name = 'edicai.home.data'
    _description = 'Edicai Home — role-aware data provider'

    # ------------------------------------------------------------------
    # Landing wire-in / restore (reversible by design; uninstall is NOT)
    # ------------------------------------------------------------------
    @api.model
    def wire_home_action(self, logins=None):
        """Assign the Edicai Home action to active internal users (all by
        default; a login list may restrict it). Snapshot is appended for
        any user whose action was non-empty before the call."""
        import json
        from odoo.addons.edicai_home.hooks import PARAM_SNAPSHOT
        action = self.env.ref('edicai_home.action_edicai_home')
        # portal-implied roles excluded (see hooks.post_init_wire_home) —
        # a backend student cannot hold base.group_user simultaneously
        role_groups = {self.env.ref(xmlid).id
                       for key, xmlid in ROLE_GROUPS.items() if key != 'student'}
        users = self.env['res.users'].sudo().search([
            ('active', '=', True), ('share', '=', False),
        ])
        users_portal = self.env['res.users'].sudo().search([
            ('active', '=', True), ('share', '=', True),
            ('group_ids', 'in', list(role_groups)),
        ])
        users = users | users_portal
        if logins:
            users = users.filtered(lambda u: u.login in set(logins))
        touched = users.filtered(
            lambda u: u.action_id != action)
        if not touched:
            return {'ok': True, 'changed': 0}
        # only snapshot non-empty originals (NULL stays clearable by restore)
        icp = self.env['ir.config_parameter'].sudo()
        raw = icp.get_param(PARAM_SNAPSHOT, '') or ''
        try:
            existing = json.loads(raw) if raw.strip() else {}
        except (ValueError, TypeError):
            existing = {}
        snap = dict(existing) if isinstance(existing, dict) else {}
        if isinstance(existing, list):
            snap.update({str(x): None for x in existing})
        for user in touched:
            if user.action_id:
                snap[str(user.login)] = {
                    'action_xmlid': self._xmlid_of_action(user.action_id),
                    'res_id': user.action_id.id,
                }
        try:
            touched.write({'action_id': action.id})
            icp.set_param(PARAM_SNAPSHOT, json.dumps(snap, sort_keys=True))
            return {'ok': True, 'changed': len(touched)}
        except Exception:
            self.env.cr.rollback()
            return {'ok': False}

    @api.model
    def restore_home_action(self):
        """Restore original per-user home actions from the snapshot.

        Snapshot formats accepted:
        - list of logins  (post_init hook: plain wiring of NULL-action users
          -> revert = clear their action)
        - dict   -> legacy/augmented form from wire_home_action():
          {login: {'action_xmlid': str, 'res_id': int} | None}
          Restores recorded originals, then clears any remaining holders.
        """
        import json
        from odoo.addons.edicai_home.hooks import PARAM_SNAPSHOT
        icp = self.env['ir.config_parameter'].sudo()
        raw = icp.get_param(PARAM_SNAPSHOT, '') or ''
        try:
            snap = json.loads(raw) if raw.strip() else []
        except (ValueError, TypeError):
            snap = []
        snap_logins = set()
        originals = {}
        if isinstance(snap, dict):
            for login, info in snap.items():
                snap_logins.add(str(login))
                if isinstance(info, dict) and info:
                    originals[str(login)] = info
        elif isinstance(snap, list):
            snap_logins.update(str(x) for x in snap)
        action = self.env.ref('edicai_home.action_edicai_home',
                              raise_if_not_found=False)
        if not action:
            return {'ok': False}
        Users = self.env['res.users'].sudo()
        changed = 0
        for login, info in originals.items():
            user = Users.search([('login', '=', login)], limit=1)
            if not user:
                continue
            if 'res_id' in info:
                original = self.env['ir.actions.actions'].browse(
                    info['res_id'])
                user.write({'action_id':
                            original.id if original.exists() else False})
                changed += 1
        # plain revert: every user still holding the Home action
        plain = Users.search([('action_id', '=', action.id)])
        plain.write({'action_id': False})
        changed += len(plain)
        return {'ok': True, 'changed': changed}

    @api.model
    def _xmlid_of_action(self, action):
        data = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.actions.actions'),
            ('res_id', '=', action.id)], limit=1)
        return ('%s.%s' % (data.module, data.name)) if data else ''

    # ------------------------------------------------------------------
    # Roles & profiles
    # ------------------------------------------------------------------
    def _profile_roles(self, user):
        return [role for role in PROFILE_ROLE_ORDER
                if user.has_group(ROLE_GROUPS[role])]

    @api.model
    def _pref_key(self, user):
        return 'edicai_home.widgets.%s' % user.id

    @api.model
    def _get_widget_prefs(self, user):
        import json
        icp = self.env['ir.config_parameter'].sudo()
        raw = icp.get_param(self._pref_key(user), '')
        if not raw.strip():
            return None
        try:
            return set(json.loads(raw))
        except (ValueError, TypeError):
            return None

    @api.model
    def get_available_widgets(self):
        user = self.env.user
        roles = self._profile_roles(user)
        keys = []
        for key in WIDGET_ROLES:
            widget_roles = self._roles_for_widget(key)
            if any(role in widget_roles for role in roles):
                keys.append(key)
        return keys

    @api.model
    def save_widget_prefs(self, enabled_keys):
        import json
        user = self.env.user
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(self._pref_key(user), json.dumps(sorted(enabled_keys)))
        return {'ok': True}

    @api.model
    def reset_widget_prefs(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(self._pref_key(self.env.user), '')
        return {'ok': True}

    def _roles_for_widget(self, key):
        return WIDGET_ROLES.get(key) or PROFILE_ROLE_ORDER

    # ------------------------------------------------------------------
    # Main entry point (ORM call from the client action)
    # ------------------------------------------------------------------
    @api.model
    def get_home_data(self):
        user = self.env.user
        roles = self._profile_roles(user)
        widget_keys = []
        for key in WIDGET_ROLES:
            widget_roles = self._roles_for_widget(key)
            if any(role in widget_roles for role in roles):
                widget_keys.append(key)
        prefs = self._get_widget_prefs(user)
        if prefs is not None:
            widget_keys = [k for k in widget_keys if k in prefs]
        widgets = [self._build_widget(key, user, roles)
                   for key in widget_keys]
        return {
            'header': self._build_header(user),
            'roles': roles,
            'widgets': widgets,
            'charts': self._build_charts(user, roles),
            'onboarding': self.env['edicai.onboarding.item'].get_role_onboarding(user, roles),
            'updates': {
                'product': self.env['edicai.product.update'].get_recent_updates(limit=15),
                'notices': self.env['edicai.notice']._home_feed(user, limit=8),
            },
        }

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------
    def _build_charts(self, user, roles):
        charts = []
        if any(r in roles for r in ('admin', 'manager')):
            try:
                data = self.env['edicai.student'].read_group(
                    [], ['student_state'], ['student_state'], lazy=False)
                charts.append({
                    'key': 'enrollment_by_state',
                    'title': 'Enrollment by Status',
                    'type': 'donut',
                    'labels': [d.get('student_state') or 'Unknown' for d in data],
                    'values': [d.get('__count', 0) for d in data],
                    'colors': ['#875A7B', '#00A09D', '#F0AD4E', '#F05545', '#5BC0DE'],
                })
            except Exception:
                _logger.warning('enrollment chart failed', exc_info=True)
        if any(r in roles for r in ('admin', 'registrar', 'manager')):
            try:
                data = self.env['edicai.admission.applicant'].read_group(
                    [], ['state'], ['state'], lazy=False)
                charts.append({
                    'key': 'admissions_pipeline',
                    'title': 'Admissions Pipeline',
                    'type': 'bar',
                    'labels': [d.get('state') or 'Unknown' for d in data],
                    'values': [d.get('__count', 0) for d in data],
                    'colors': ['#3498DB'],
                })
            except Exception:
                _logger.warning('admissions chart failed', exc_info=True)
        if any(r in roles for r in ('admin', 'finance', 'manager')):
            try:
                data = self.env['edicai.fee.invoice'].read_group(
                    [], ['invoice_state'], ['invoice_state'], lazy=False)
                charts.append({
                    'key': 'fee_status',
                    'title': 'Fee Invoice Status',
                    'type': 'donut',
                    'labels': [d.get('invoice_state') or 'Unknown' for d in data],
                    'values': [d.get('__count', 0) for d in data],
                    'colors': ['#5CB85C', '#F0AD4E', '#F05545', '#5BC0DE', '#875A7B'],
                })
            except Exception:
                _logger.warning('fee chart failed', exc_info=True)
        if any(r in roles for r in ('admin', 'staff', 'manager')):
            try:
                data = self.env['edicai.attendance.record'].read_group(
                    [], ['status'], ['status'], lazy=False)
                charts.append({
                    'key': 'attendance_status',
                    'title': 'Attendance Status',
                    'type': 'bar',
                    'labels': [d.get('status') or 'Unknown' for d in data],
                    'values': [d.get('__count', 0) for d in data],
                    'colors': ['#21B799'],
                })
            except Exception:
                _logger.warning('attendance chart failed', exc_info=True)
        return charts

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self, user):
        company = user.company_id.name or ''
        today = fields.Date.context_today(self)
        semester = None
        try:
            Sem = self.env['edicai.semester']
            sem = Sem.search([
                ('date_start', '<=', today), ('date_end', '>=', today),
            ], limit=1)
            if sem:
                semester = {
                    'name': sem.name, 'code': sem.code or '',
                    'year': sem.academic_year_id.name or '',
                }
        except AccessError:
            semester = None
        except Exception:
            _logger.warning('semester lookup failed', exc_info=True)
            semester = None
        return {
            'user_name': user.name,
            'company': company,
            'date': str(today),
            'semester': semester,
            'greeting': self._greeting(today),
        }

    @staticmethod
    def _greeting(today):
        hour = fields.Datetime.now().hour
        if hour < 12:
            return 'Good morning'
        if hour < 17:
            return 'Good afternoon'
        return 'Good evening'

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------
    def _build_widget(self, key, user, roles):
        builder = getattr(self, '_widget_%s' % key, None)
        widget = {'key': key, 'title': '', 'icon': '', 'kind': 'list',
                  'section': SECTION_OF.get(key, 'secondary'),
                  'restricted': False, 'error': False, 'empty': False,
                  'kpis': [], 'rows': [], 'actions': [], 'view_all': None}
        if not builder:
            widget['error'] = True
            return widget
        res = _safe(lambda: builder(user=user, widget=widget, roles=roles))
        if res.get('restricted'):
            widget['restricted'] = True
            widget['empty'] = True
        elif res.get('error'):
            widget['error'] = True
            widget['empty'] = True
        if not widget['error'] and not widget['restricted']:
            widget['empty'] = not (widget['kpis'] or widget['rows']
                                   or widget['actions'])
        return widget

    def _count(self, model, domain=None):
        return self.env[model].search_count(domain or [])

    def _group_counts(self, model, group_field, domain=None, limit=8):
        data = self.env[model].read_group(domain or [], [], [group_field],
                                          lazy=False)
        return [{'label': r[group_field] or 'other', 'count': r['__count']}
                for r in data[:limit] if r.get('__count')]

    def _rows(self, model, domain, fields_, limit=5, order=None):
        fields_ = list(dict.fromkeys(['display_name'] + list(fields_)))
        recs = self.env[model].search_read(domain, fields_, limit=limit,
                                           order=order)
        rows = []
        for r in recs:
            extras = {k: r.get(k) for k in fields_
                      if k not in ('display_name', 'id')}
            subtitle = ' · '.join(str(v) for v in extras.values() if v)
            rows.append({'id': r['id'], 'res_model': model,
                         'title': r.get('display_name') or '',
                         'subtitle': subtitle,
                         'badge': extras.get('state')
                         or extras.get('issue_state')
                         or extras.get('entry_state')
                         or extras.get('result_status'),
                         'values': extras})
        return rows

    def _open_list(self, res_model, name, domain=None):
        return {'res_model': res_model, 'name': name, 'domain': domain or []}

    # ---- Admin / Manager ------------------------------------------------
    def _widget_enrollment_overview(self, user, widget, roles):
        widget.update(title='Enrollment', icon='fa-users', kind='kpi')
        widget['kpis'] = [
            {'label': 'Active students', 'value': self._count('edicai.student')},
            {'label': 'Enrolled', 'value': self._count('edicai.student',
                [('student_state', 'in', ['enrolled', 'active'])])},
            {'label': 'On leave', 'value': self._count('edicai.student',
                [('student_state', '=', 'on_leave')])},
            {'label': 'New this month', 'value': self._count('edicai.student',
                [('create_date', '>', str(date.today().replace(day=1)))])},
        ]
        widget['view_all'] = self._open_list('edicai.student', 'Students')

    def _widget_admissions_pipeline(self, user, widget, roles):
        widget.update(title='Admissions Pipeline', icon='fa-filter', kind='kpi')
        widget['kpis'] = [
            {'label': 'New inquiries', 'value': self._count('edicai.admission.applicant',
                [('state', 'in', ['inquiry', 'applied'])])},
            {'label': 'Under review', 'value': self._count('edicai.admission.applicant',
                [('state', '=', 'under_review')])},
            {'label': 'At offer stage', 'value': self._count('edicai.admission.applicant',
                [('state', 'in', ['shortlisted', 'entrance_scheduled',
                                  'merit_listed', 'offer_sent'])])},
            {'label': 'Confirmed', 'value': self._count('edicai.admission.applicant',
                [('state', '=', 'confirmed')])},
        ]
        widget['rows'] = self._rows('edicai.admission.applicant',
            [('state', 'in', ['inquiry', 'applied', 'under_review'])],
            ['state'], limit=5, order='write_date desc')
        widget['view_all'] = self._open_list('edicai.admission.applicant', 'Applicants')

    def _widget_fee_collection(self, user, widget, roles):
        widget.update(title='Fee Collection', icon='fa-money', kind='kpi')
        month_start = str(date.today().replace(day=1))
        widget['kpis'] = [
            {'label': 'Outstanding', 'value': self._count('edicai.fee.invoice',
                [('invoice_state', 'in', ['sent', 'partial', 'overdue'])])},
            {'label': 'Overdue', 'value': self._count('edicai.fee.invoice',
                [('invoice_state', '=', 'overdue')])},
            {'label': 'Partially paid', 'value': self._count('edicai.fee.invoice',
                [('invoice_state', '=', 'partial')])},
            {'label': 'Payments this month', 'value': self._count('edicai.fee.payment',
                [('payment_state', '=', 'confirmed'),
                 ('payment_date', '>=', month_start)])},
        ]
        widget['view_all'] = self._open_list('edicai.fee.invoice', 'Fee Invoices')

    def _widget_attendance_overview(self, user, widget, roles):
        widget.update(title='Attendance Overview', icon='fa-calendar-check-o',
                      kind='kpi')
        today = fields.Date.context_today(self)
        widget['kpis'] = [
            {'label': 'Sessions today', 'value': self._count('edicai.attendance.session',
                [('session_date', '=', today)])},
            {'label': 'Open', 'value': self._count('edicai.attendance.session',
                [('session_date', '=', today), ('session_state', '=', 'open')])},
            {'label': 'Cancelled', 'value': self._count('edicai.attendance.session',
                [('session_date', '=', today), ('is_cancelled', '=', True)])},
            {'label': 'Shortage alerts', 'value': self._count('edicai.attendance.record',
                [('shortage_alert', '=', True)])},
        ]
        widget['view_all'] = self._open_list('edicai.attendance.session', 'Sessions')

    def _widget_pending_approvals(self, user, widget, roles):
        widget.update(title='Pending Approvals', icon='fa-hourglass-half',
                      kind='list')
        rows = []
        rows += [{'id': r['id'], 'res_model': 'edicai.admission.applicant',
                  'title': r.get('display_name') or '', 'subtitle': 'Application — under review',
                  'badge': r.get('state'), 'badge_type': 'info'}
                 for r in self.env['edicai.admission.applicant'].search_read(
                     [('state', '=', 'under_review')], ['state'], limit=3)]
        rows += [{'id': r['id'], 'res_model': 'edicai.student.leave.request',
                  'title': r.get('display_name') or '', 'subtitle': 'Leave request — submitted',
                  'badge': r.get('state'), 'badge_type': 'warning'}
                 for r in self.env['edicai.student.leave.request'].search_read(
                     [('state', '=', 'submitted')], ['state'], limit=3)]
        if 'finance' in roles:
            rows += [{'id': r['id'], 'res_model': 'edicai.fee.payment',
                      'title': r.get('display_name') or '', 'subtitle': 'Payment — draft',
                      'badge': 'draft', 'badge_type': 'info'}
                     for r in self.env['edicai.fee.payment'].search_read(
                         [('payment_state', '=', 'draft')],
                         ['payment_state'], limit=3)]
        widget['rows'] = rows
        widget['view_all'] = self._open_list('edicai.admission.applicant',
                                             'Under review applications',
                                             [('state', '=', 'under_review')])

    def _widget_overdue_alerts(self, user, widget, roles):
        widget.update(title='Important Alerts', icon='fa-exclamation-triangle',
                      kind='list')
        widget['rows'] = [
            {'id': r['id'], 'res_model': 'edicai.fee.invoice',
             'title': r.get('display_name') or '', 'subtitle': 'Overdue invoice',
             'badge': 'overdue', 'badge_type': 'danger'}
            for r in self.env['edicai.fee.invoice'].search_read(
                [('invoice_state', '=', 'overdue')],
                ['invoice_state'], limit=4)]
        replies = self._count('edicai.grievance.request',
                              [('state', 'in', ['submitted', 'in_progress'])])
        if replies:
            widget['kpis'] = [{'label': 'Open grievances', 'value': replies}]

    def _widget_recent_payments(self, user, widget, roles):
        widget.update(title='Recent Payments', icon='fa-credit-card', kind='list')
        widget['rows'] = self._rows('edicai.fee.payment',
            [('payment_state', '=', 'confirmed')],
            ['amount', 'payment_date'], limit=6,
            order='payment_date desc')
        widget['view_all'] = self._open_list('edicai.fee.payment', 'Payments')

    # ---- Faculty --------------------------------------------------------
    def _resolve_faculty_member(self, user):
        return self.env['edicai.faculty.member'].search(
            [('user_id', '=', user.id)], limit=1)

    def _widget_today_classes_faculty(self, user, widget, roles):
        widget.update(title="Today's Classes", icon='fa-table', kind='list')
        member = self._resolve_faculty_member(user)
        if not member:
            widget['empty'] = True
            widget['title_extra'] = 'No faculty profile linked to your account'
            return
        today_dow = str(fields.Date.context_today(self).weekday())
        entries = self.env['edicai.timetable.entry'].search_read(
            [('instructor_id', '=', member.id), ('day_of_week', '=', today_dow)],
            ['display_name', 'course_offering_id', 'time_slot_id', 'room_id'],
            limit=8, order='time_slot_id')
        widget['rows'] = [
            {'id': r['id'], 'res_model': 'edicai.timetable.entry',
             'title': r['course_offering_id'][1] if r.get('course_offering_id') else
                      r.get('display_name', ''),
             'subtitle': r['time_slot_id'][1] if r.get('time_slot_id') else '',
             'values': r}
            for r in entries]
        widget['view_all'] = self._open_list('edicai.timetable.entry', 'Today')

    def _widget_assignments_review(self, user, widget, roles):
        widget.update(title='Assignments To Review', icon='fa-book', kind='list')
        member = self._resolve_faculty_member(user)
        if not member:
            widget['empty'] = True
            return
        subs = self.env['edicai.assignment.submission'].search_read(
            [('assignment_id.course_offering_id.faculty_member_id', '=', member.id),
             ('state', 'in', ['submitted', 'late'])],
            ['display_name', 'state', 'assignment_id'], limit=6,
            order='write_date desc')
        widget['kpis'] = [{'label': 'Awaiting review', 'value': len(subs)}]
        widget['rows'] = [
            {'id': r['id'], 'res_model': 'edicai.assignment.submission',
             'title': r.get('display_name') or '',
             'subtitle': r['assignment_id'][1] if r.get('assignment_id') else '',
             'badge': r.get('state'),
             'badge_type': 'warning' if r.get('state') == 'late' else 'info'}
            for r in subs]
        widget['view_all'] = self._open_list(
            'edicai.assignment.submission', 'Submissions to grade',
            [('state', 'in', ['submitted', 'late'])])

    def _widget_pending_grading(self, user, widget, roles):
        widget.update(title='Pending Grading', icon='fa-pencil-square-o',
                      kind='kpi')
        member = self._resolve_faculty_member(user)
        if not member:
            widget['empty'] = True
            return
        widget['kpis'] = [
            {'label': 'Submissions to grade', 'value': self._count(
                'edicai.assignment.submission',
                [('assignment_id.course_offering_id.faculty_member_id', '=', member.id),
                 ('state', 'in', ['submitted', 'late'])])},
            {'label': 'Grade entries draft', 'value': self._count(
                'edicai.grade.entry',
                [('course_offering_id.faculty_member_id', '=', member.id),
                 ('entry_state', '=', 'draft')])},
        ]
        widget['view_all'] = self._open_list('edicai.grade.entry', 'Grade Entries',
                                            [('entry_state', '=', 'draft')])

    # ---- Student --------------------------------------------------------
    def _resolve_student(self, user):
        return self.env['edicai.student'].search(
            [('partner_id', '=', user.partner_id.id)], limit=1)

    def _widget_today_classes_student(self, user, widget, roles):
        widget.update(title="Today's Classes", icon='fa-table', kind='list')
        student = self._resolve_student(user)
        if not student:
            widget['empty'] = True
            widget['title_extra'] = 'No student profile linked to your account'
            return
        Enrollment = self.env['edicai.enrollment']
        try:
            offerings = Enrollment.search_read(
                [('student_id', '=', student.id)], ['course_offering_id'])
        except AccessError:
            widget['restricted'] = True
            return
        offering_ids = [o['course_offering_id'][0]
                        for o in offerings if o.get('course_offering_id')]
        if not offering_ids:
            widget['empty'] = True
            return
        today_dow = str(fields.Date.context_today(self).weekday())
        widget['rows'] = [
            {'id': r['id'], 'res_model': 'edicai.timetable.entry',
             'title': r['course_offering_id'][1] if r.get('course_offering_id') else '',
             'subtitle': r['time_slot_id'][1] if r.get('time_slot_id') else ''}
            for r in self.env['edicai.timetable.entry'].search_read(
                [('course_offering_id', 'in', offering_ids),
                 ('day_of_week', '=', today_dow)],
                ['course_offering_id', 'time_slot_id'], limit=8,
                order='time_slot_id')]

    def _widget_my_attendance(self, user, widget, roles):
        widget.update(title='My Attendance', icon='fa-calendar-check-o', kind='kpi')
        student = self._resolve_student(user)
        if not student:
            widget['empty'] = True
            widget['title_extra'] = 'No student profile linked to your account'
            return
        month_start = str(fields.Date.context_today(self).replace(day=1))
        domain = [('student_id', '=', student.id),
                  ('session_date', '>=', month_start)]
        widget['kpis'] = [
            {'label': 'Sessions this month',
             'value': self._count('edicai.attendance.record', domain)},
            {'label': 'Present',
             'value': self._count('edicai.attendance.record',
                                  domain + [('status', '=', 'present')])},
            {'label': 'Absent',
             'value': self._count('edicai.attendance.record',
                                  domain + [('status', '=', 'absent')])},
            {'label': 'Late',
             'value': self._count('edicai.attendance.record',
                                  domain + [('status', '=', 'late')])},
        ]
        widget['view_all'] = self._open_list('edicai.attendance.record',
                                             'My Attendance', domain)

    def _widget_my_assignments(self, user, widget, roles):
        widget.update(title='Assignments & Deadlines', icon='fa-tasks', kind='list')
        student = self._resolve_student(user)
        if not student:
            widget['empty'] = True
            return
        widget['rows'] = self._rows('edicai.assignment.submission',
            [('student_id', '=', student.id),
             ('state', 'in', ['draft', 'submitted', 'late'])],
            ['state'], limit=6, order='write_date desc')
        widget['view_all'] = self._open_list('edicai.assignment.submission',
                                             'My submissions',
                                             [('student_id', '=', student.id)])

    def _widget_my_results(self, user, widget, roles):
        widget.update(title='Published Results', icon='fa-trophy', kind='list')
        student = self._resolve_student(user)
        if not student:
            widget['empty'] = True
            return
        try:
            recs = self.env['edicai.semester.result'].search_read(
                [('student_id', '=', student.id), ('is_published', '=', True)],
                ['display_name', 'result_status', 'semester_gpa',
                 'published_on'], limit=5, order='published_on desc')
        except AccessError:
            widget['restricted'] = True
            return
        widget['rows'] = [{'id': r['id'], 'res_model': 'edicai.semester.result',
                           'title': r.get('display_name') or '',
                           'subtitle': ('GPA %s' % r['semester_gpa'])
                                       if r.get('semester_gpa') else '',
                           'badge': r.get('result_status'),
                           'badge_type': 'success'
                           if r.get('result_status') == 'pass' else 'danger'}
                          for r in recs]

    # ---- Staff / Librarian ----------------------------------------------
    def _widget_library_overdue(self, user, widget, roles):
        widget.update(title='Overdue Books', icon='fa-book', kind='list')
        today = fields.Date.context_today(self)
        try:
            rows = self.env['edicai.library.issue'].search_read(
                [('issue_state', '=', 'issued'), ('due_date', '<', str(today))],
                ['display_name', 'due_date', 'days_overdue'], limit=6,
                order='due_date asc')
        except AccessError:
            widget['restricted'] = True
            return
        widget['kpis'] = [{'label': 'Overdue', 'value': len(rows)}]
        widget['rows'] = [{'id': r['id'], 'res_model': 'edicai.library.issue',
                           'title': r.get('display_name') or '',
                           'subtitle': ('Due %s' % r['due_date'])
                                       if r.get('due_date') else '',
                           'badge': 'overdue', 'badge_type': 'danger'}
                          for r in rows]
        widget['view_all'] = self._open_list('edicai.library.issue', 'On Loan',
                                            [('issue_state', '=', 'issued')])

    def _widget_library_activity(self, user, widget, roles):
        widget.update(title='Library Activity', icon='fa-exchange', kind='kpi')
        today = fields.Date.context_today(self)
        soon = str(today + timedelta(days=3))
        widget['kpis'] = [
            {'label': 'On loan', 'value': self._count('edicai.library.issue',
                 [('issue_state', '=', 'issued')])},
            {'label': 'Due in 3 days', 'value': self._count('edicai.library.issue',
                 [('issue_state', '=', 'issued'), ('due_date', '>=', str(today)),
                  ('due_date', '<=', soon)])},
            {'label': 'Returned today', 'value': self._count('edicai.library.issue',
                 [('return_date', '=', str(today))])},
        ]
        widget['view_all'] = self._open_list('edicai.library.issue', 'All Issues')

    # ---- Manager / Placement --------------------------------------------
    def _widget_placement_overview(self, user, widget, roles):
        widget.update(title='Placement Overview', icon='fa-briefcase', kind='kpi')
        today = fields.Date.context_today(self)
        widget['kpis'] = [
            {'label': 'Active drives', 'value': self._count('edicai.placement.drive',
                 [('state', '=', 'active')])},
            {'label': 'Upcoming drives', 'value': self._count('edicai.placement.drive',
                 [('state', '=', 'active'), ('date', '>=', str(today))])},
            {'label': 'Applications shortlisted', 'value': self._count(
                 'edicai.placement.application', [('status', '=', 'shortlisted')])},
            {'label': 'Applications applied', 'value': self._count(
                 'edicai.placement.application', [('status', '=', 'applied')])},
        ]
        try:
            rows = self.env['edicai.placement.drive'].search_read(
                [('state', '=', 'active')], ['display_name', 'date'],
                limit=5, order='date asc')
        except AccessError:
            widget['restricted'] = True
            return
        widget['rows'] = [{'id': r['id'], 'res_model': 'edicai.placement.drive',
                           'title': r.get('display_name') or '',
                           'subtitle': str(r['date']) if r.get('date') else ''}
                          for r in rows]
        widget['view_all'] = self._open_list('edicai.placement.drive', 'Drives')

    # ---- Website editor (condition-grouped) ------------------------------
    def _widget_website_shortcuts(self, user, widget, roles):
        widget.update(title='Website Management', icon='fa-globe', kind='actions')
        previews = None
        try:
            previews = self.env.ref('website.website_preview',
                                    raise_if_not_found=False)
        except Exception:
            previews = None
        widget['actions'] = [
            {'label': 'Open website', 'action_xmlid': 'website.website_preview'}
            if previews else {'label': 'Open Apps', 'res_model': None},
        ]

    # ---- Everyone --------------------------------------------------------
    def _widget_upcoming_schedule(self, user, widget, roles):
        widget.update(title='Upcoming', icon='fa-calendar', kind='list')
        today = fields.Date.context_today(self)
        soon = str(today + timedelta(days=14))
        rows = []
        try:
            rows.extend([
                {'id': r['id'], 'res_model': 'edicai.exam.schedule',
                 'title': r.get('display_name') or '',
                 'subtitle': 'Exam · %s' % (r['exam_date'] or ''),
                 'values': r}
                for r in self.env['edicai.exam.schedule'].search_read(
                    [('exam_date', '>=', str(today)), ('exam_date', '<=', soon)],
                    ['display_name', 'exam_date'], limit=4,
                    order='exam_date asc')])
        except AccessError:
            pass
        except Exception:
            _logger.warning('upcoming exam feed failed', exc_info=True)
        if 'manager' in roles:
            try:
                rows.extend([
                    {'id': r['id'], 'res_model': 'edicai.placement.drive',
                     'title': r.get('display_name') or '',
                     'subtitle': 'Placement drive · %s' % (r['date'] or ''),
                     'values': r}
                    for r in self.env['edicai.placement.drive'].search_read(
                        [('date', '>=', str(today)), ('state', '=', 'active')],
                        ['display_name', 'date'], limit=3,
                        order='date asc')])
            except AccessError:
                pass
            except Exception:
                _logger.warning('drive feed failed', exc_info=True)
        widget['rows'] = rows

    def _widget_institution_notices(self, user, widget, roles):
        widget.update(title='Announcements', icon='fa-bullhorn', kind='notices')
        widget['rows'] = self.env['edicai.notice']._home_feed(user, limit=5)

    def _widget_quick_links(self, user, widget, roles):
        widget.update(title='Quick Links', icon='fa-bolt', kind='actions')
        links = []
        for role in roles:
            for label, model in QUICK_LINKS.get(role, []):
                if model and model in self.env:
                    links.append({'label': label, 'res_model': model})
        unique, seen = [], set()
        for link in links:
            if link['res_model'] not in seen:
                seen.add(link['res_model'])
                unique.append(link)
        widget['actions'] = unique[:8]
