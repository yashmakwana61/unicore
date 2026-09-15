import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class OacisOverviewDashboard(models.Model):
    """Dashboard aggregation for Oacis Overview (oacis_base)."""
    _name = 'oacis.overview.dashboard'
    _description = 'Oacis Overview Dashboard (transient)'

    @api.model
    def get_overview_data(self, domain=None, company_id=None, campus_id=None):
        """Aggregate KPIs across SIS modules for Overview dashboard.

        :param domain: optional extra domain (not used heavily, kept for parity)
        :param company_id: filter by institution res.company id
        :param campus_id: filter by oacis.campus id
        :return: dict with kpis, charts, tables
        """
        if domain is None:
            domain = []

        base_domain = []
        if company_id:
            # campus and student etc filter by company_id if model has it
            base_domain = []  # handled per model

        data = {
            'kpis': {},
            'charts': {},
            'tables': {},
        }

        # Helper safe wrappers
        def safe_count(model_name, extra_domain=None):
            try:
                if model_name not in self.env:
                    return 0
                dom = list(extra_domain or [])
                # apply company/campus filter if field exists
                Model = self.env[model_name]
                # infer filter field existence via _fields
                if company_id and 'company_id' in Model._fields:
                    dom.append(('company_id', '=', company_id))
                if campus_id and 'campus_id' in Model._fields:
                    dom.append(('campus_id', '=', campus_id))
                # also try x_company etc? keep simple
                return Model.search_count(dom)
            except Exception as e:
                _logger.warning("Overview safe_count %s failed: %s", model_name, e)
                return 0

        def safe_read_group(model_name, fields, groupby, domain_extra=None, orderby=None):
            try:
                if model_name not in self.env:
                    return []
                Model = self.env[model_name]
                dom = list(domain_extra or [])
                if company_id and 'company_id' in Model._fields:
                    dom.append(('company_id', '=', company_id))
                if campus_id and 'campus_id' in Model._fields:
                    dom.append(('campus_id', '=', campus_id))
                return Model.read_group(dom, fields, groupby, orderby=orderby, lazy=False)
            except Exception as e:
                _logger.warning("Overview read_group %s failed: %s", model_name, e)
                return []

        # ============================================================
        # KPIs
        # ============================================================
        # Campuses
        total_campuses = safe_count('oacis.campus')
        active_campuses = safe_count('oacis.campus', [('active', '=', True)])
        campuses_by_type = safe_read_group('oacis.campus', ['campus_type'], ['campus_type'])

        # Companies / Institutions
        total_institutions = safe_count('res.company')

        # Students
        total_students = safe_count('oacis.student')
        active_students = safe_count('oacis.student', [('student_state', '=', 'active')])
        on_leave_students = safe_count('oacis.student', [('student_state', '=', 'on_leave')])
        graduated_students = safe_count('oacis.student', [('student_state', '=', 'graduated')])

        # Applicants
        total_applicants = safe_count('oacis.admission.applicant')
        # reuse funnel states if available
        confirmed_applicants = safe_count('oacis.admission.applicant', [('state', '=', 'confirmed')])

        # Faculty members
        total_faculty = safe_count('oacis.faculty.member')
        active_faculty = safe_count('oacis.faculty.member', [('member_state', '=', 'active')])

        # Programs
        total_programs = safe_count('oacis.program')
        active_programs = safe_count('oacis.program', [('program_state', '=', 'active')])

        # Fees
        total_invoices = safe_count('oacis.fee.invoice')
        overdue_invoices = safe_count('oacis.fee.invoice', [('invoice_state', '=', 'overdue')])
        # sums
        outstanding_amount = 0
        try:
            if 'oacis.fee.invoice' in self.env:
                Model = self.env['oacis.fee.invoice']
                dom = []
                if company_id and 'company_id' in Model._fields:
                    dom.append(('company_id', '=', company_id))
                if campus_id and 'campus_id' in Model._fields:
                    dom.append(('campus_id', '=', campus_id))
                # only outstanding
                dom += [('invoice_state', 'in', ['sent', 'partial', 'overdue'])]
                invoices = Model.search(dom)
                # try fields amount_outstanding / total_amount
                if invoices:
                    if 'amount_outstanding' in Model._fields:
                        outstanding_amount = sum(invoices.mapped('amount_outstanding') or [0])
                    elif 'total_amount' in Model._fields:
                        outstanding_amount = sum(invoices.mapped('total_amount') or [0])
        except Exception as e:
            _logger.warning("Outstanding fees calc failed: %s", e)

        # Attendance sessions
        total_sessions = safe_count('oacis.attendance.session')
        open_sessions = safe_count('oacis.attendance.session', [('session_state', '=', 'open')])
        closed_sessions = safe_count('oacis.attendance.session', [('session_state', '=', 'closed')])

        # Shortage alerts
        shortage_alerts = safe_count('oacis.attendance.record', [('shortage_alert', '=', True)])

        data['kpis'] = {
            'total_institutions': total_institutions,
            'total_campuses': total_campuses,
            'active_campuses': active_campuses,
            'total_students': total_students,
            'active_students': active_students,
            'on_leave_students': on_leave_students,
            'graduated_students': graduated_students,
            'total_applicants': total_applicants,
            'confirmed_applicants': confirmed_applicants,
            'total_faculty': total_faculty,
            'active_faculty': active_faculty,
            'total_programs': total_programs,
            'active_programs': active_programs,
            'total_invoices': total_invoices,
            'overdue_invoices': overdue_invoices,
            'outstanding_amount': round(outstanding_amount, 2),
            'total_sessions': total_sessions,
            'open_sessions': open_sessions,
            'closed_sessions': closed_sessions,
            'shortage_alerts': shortage_alerts,
        }

        # ============================================================
        # Charts data
        # ============================================================
        # Students by state
        students_by_state = safe_read_group('oacis.student', ['student_state'], ['student_state'])
        data['charts']['students_by_state'] = [
            {'state': x['student_state'], 'label': x.get('student_state:count') and x['student_state'] or 'Unknown', 'count': x['student_state:count'] if 'student_state:count' in x else x.get('__count', x.get('student_state_count', 0))}
            for x in students_by_state
        ]
        # Better: use direct count field mapping from read_group structure
        # read_group returns {'student_state': 'active', 'student_state_count': 12}
        # Normalize
        normalized = []
        for x in students_by_state:
            cnt = x.get('student_state_count', x.get('__count', 0))
            normalized.append({'state': x['student_state'], 'label': x['student_state'] or 'Unknown', 'count': cnt})
        data['charts']['students_by_state'] = normalized

        # Students by campus
        students_by_campus = safe_read_group('oacis.student', ['campus_id'], ['campus_id'])
        data['charts']['students_by_campus'] = [
            {'campus_id': x['campus_id'][0] if x['campus_id'] else None, 'campus_name': x['campus_id'][1] if x['campus_id'] else 'Unknown', 'count': x.get('campus_id_count', x.get('__count', 0))}
            for x in students_by_campus
        ]

        # Students by program
        students_by_program = safe_read_group('oacis.student', ['program_id'], ['program_id'])
        data['charts']['students_by_program'] = [
            {'program_id': x['program_id'][0] if x['program_id'] else None, 'program_name': x['program_id'][1] if x['program_id'] else 'Unknown', 'count': x.get('program_id_count', x.get('__count', 0))}
            for x in students_by_program
        ]

        # Campuses by type
        data['charts']['campuses_by_type'] = [
            {'campus_type': x['campus_type'], 'label': x['campus_type'] or 'Unknown', 'count': x.get('campus_type_count', x.get('__count', 0))}
            for x in campuses_by_type
        ]

        # Applicants by state (reuse applicant read_group)
        applicants_by_state = safe_read_group('oacis.admission.applicant', ['state'], ['state'])
        data['charts']['applicants_by_state'] = [
            {'state': x['state'], 'label': x['state'] or 'Unknown', 'count': x.get('state_count', x.get('__count', 0))}
            for x in applicants_by_state
        ]

        # Invoices by state
        invoices_by_state = safe_read_group('oacis.fee.invoice', ['invoice_state'], ['invoice_state'])
        data['charts']['invoices_by_state'] = [
            {'invoice_state': x['invoice_state'], 'label': x['invoice_state'] or 'Unknown', 'count': x.get('invoice_state_count', x.get('__count', 0))}
            for x in invoices_by_state
        ]

        # Attendance sessions by state
        sessions_by_state = safe_read_group('oacis.attendance.session', ['session_state'], ['session_state'])
        data['charts']['sessions_by_state'] = [
            {'session_state': x['session_state'], 'label': x['session_state'] or 'Unknown', 'count': x.get('session_state_count', x.get('__count', 0))}
            for x in sessions_by_state
        ]

        # ============================================================
        # Tables: recent records (5 each)
        # ============================================================
        try:
            if 'oacis.admission.applicant' in self.env:
                Model = self.env['oacis.admission.applicant']
                dom = []
                if company_id and 'company_id' in Model._fields:
                    dom.append(('company_id', '=', company_id))
                if campus_id and 'campus_id' in Model._fields:
                    dom.append(('campus_id', '=', campus_id))
                recs = Model.search(dom, order='create_date desc', limit=5)
                data['tables']['recent_applicants'] = [
                    {'id': r.id, 'name': r.display_name, 'state': r.state if 'state' in r._fields else '', 'program': r.program_id.display_name if 'program_id' in r._fields and r.program_id else ''}
                    for r in recs
                ]
            else:
                data['tables']['recent_applicants'] = []
        except Exception:
            data['tables']['recent_applicants'] = []

        try:
            if 'oacis.fee.invoice' in self.env:
                Model = self.env['oacis.fee.invoice']
                dom = [('invoice_state', '=', 'overdue')] if 'invoice_state' in Model._fields else []
                if company_id and 'company_id' in Model._fields:
                    dom.append(('company_id', '=', company_id))
                recs = Model.search(dom, order='due_date asc', limit=5)
                data['tables']['overdue_invoices'] = [
                    {'id': r.id, 'name': r.display_name, 'student': r.student_id.display_name if 'student_id' in r._fields and r.student_id else '', 'amount': getattr(r, 'amount_outstanding', getattr(r, 'total_amount', 0))}
                    for r in recs
                ]
            else:
                data['tables']['overdue_invoices'] = []
        except Exception:
            data['tables']['overdue_invoices'] = []

        try:
            if 'oacis.attendance.session' in self.env:
                Model = self.env['oacis.attendance.session']
                dom = []
                if campus_id and 'campus_id' in Model._fields:
                    dom.append(('campus_id', '=', campus_id))
                recs = Model.search(dom, order='session_date desc', limit=5)
                data['tables']['recent_sessions'] = [
                    {'id': r.id, 'name': r.display_name, 'date': str(r.session_date) if 'session_date' in r._fields and r.session_date else '', 'state': r.session_state if 'session_state' in r._fields else ''}
                    for r in recs
                ]
            else:
                data['tables']['recent_sessions'] = []
        except Exception:
            data['tables']['recent_sessions'] = []

        return data
