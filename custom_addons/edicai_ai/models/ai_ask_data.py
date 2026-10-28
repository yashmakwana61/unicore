"""Ask-Data: read-only natural-language analytics over an allow-list.

Only the analytics VIEWs / finance snapshot-KPI sources listed in
``ALLOW_LIST`` can ever be queried.  A question is mapped to one intent
(keyword scoring), the intent maps to a fixed table + fixed column set,
and the SQL is *built* — never parsed from user input.  User input only
ever lands in:

* the detected intent (keyword match, not SQL),
* equality filter **values** (bound parameters ``%(f_<col>)s``),
* an integer LIMIT clamped to ``MAX_LIMIT``.

Every statement is ``SELECT <fixed cols> FROM <allow-listed table>
WHERE company_id = %(company_id)s ... LIMIT n`` with all identifiers
validated against ``^[A-Za-z_][A-Za-z0-9_]*$``.  Before execution the
built statement is re-scanned for forbidden tokens
(INSERT/UPDATE/DELETE/DROP/… ``;`` ``--`` ``/* */``); anything matching
is rejected and never reaches the cursor.

``company_id`` is mandatory and injected from ``env.company`` by the
caller (``edicai.ai.tool.registry.execute_tool`` forces it); a plan with
no company is refused.
"""

import logging
import re

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MAX_LIMIT = 500
DEFAULT_LIMIT = 100

_FORBIDDEN_RE = re.compile(
    r'\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|'
    r'execute|call|do|copy|vacuum|comment|merge|handler|load|unload|'
    r'select\s+.*\s+into)\b|--|/\*|\*/|;',
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# Maps to ``edicai_analytics/models/*.py`` VIEWs (postgres table names) plus
# the ``edicai_finance_report`` snapshot/KPI tables.
ALLOW_LIST = {
    'enrollment': {
        'label': 'Student Enrollment',
        'model': 'edicai.student.enrollment.report',
        'table': 'edicai_student_enrollment_report',
        'columns': ['program_id', 'batch_year', 'cohort_kind',
                    'grade_level_id', 'cohort_start_date', 'gender',
                    'student_state', 'student_count', 'avg_cgpa',
                    'max_cgpa', 'min_cgpa', 'avg_credits_earned'],
        'dimensions': ['program_id', 'batch_year', 'gender',
                       'student_state', 'cohort_kind'],
        'metrics': ['student_count', 'avg_cgpa'],
        'time_col': 'cohort_start_date',
        'keywords': ('enrol', 'admission intake', 'batch', 'cohort',
                     'students per program', 'cgpa', 'demographic'),
    },
    'attendance': {
        'label': 'Attendance',
        'model': 'edicai.attendance.report',
        'table': 'edicai_attendance_report',
        'columns': ['course_offering_id', 'course_id', 'semester_id',
                    'student_count', 'shortage_count',
                    'avg_attendance_pct', 'min_attendance_pct',
                    'shortage_rate'],
        'dimensions': ['course_id', 'semester_id', 'course_offering_id'],
        'metrics': ['avg_attendance_pct', 'shortage_rate',
                    'shortage_count'],
        'time_col': None,
        'keywords': ('attend', 'shortage', 'absent', 'presence'),
    },
    'grades': {
        'label': 'Grade Distribution',
        'model': 'edicai.grade.distribution.report',
        'table': 'edicai_grade_distribution_report',
        'columns': ['course_id', 'semester_id', 'letter_grade',
                    'student_count', 'pass_count', 'fail_count',
                    'avg_percentage', 'avg_grade_point', 'pass_rate'],
        'dimensions': ['course_id', 'semester_id', 'letter_grade'],
        'metrics': ['pass_rate', 'avg_percentage', 'student_count'],
        'time_col': None,
        'keywords': ('grade', 'pass rate', 'fail', 'letter grade',
                     'gpa distribution', 'course performance', 'marks'),
    },
    'semester_results': {
        'label': 'Semester Results',
        'model': 'edicai.semester.result.report',
        'table': 'edicai_semester_result_report',
        'columns': ['semester_id', 'program_id', 'result_status',
                    'student_count', 'avg_semester_gpa',
                    'avg_credits_earned'],
        'dimensions': ['semester_id', 'program_id', 'result_status'],
        'metrics': ['student_count', 'avg_semester_gpa'],
        'time_col': None,
        'keywords': ('semester result', 'sgpa', 'semester gpa',
                     'supplementary', 'result status', 'promotion'),
    },
    'admission_funnel': {
        'label': 'Admission Funnel',
        'model': 'edicai.admission.funnel.report',
        'table': 'edicai_admission_funnel_report',
        'columns': ['cycle_id', 'academic_year_id', 'program_id',
                    'total_applications', 'shortlisted', 'offer_sent',
                    'confirmed', 'rejected', 'withdrawn',
                    'shortlist_rate', 'offer_conversion_rate',
                    'admission_rate', 'avg_entrance_score',
                    'avg_aggregate_pct'],
        'dimensions': ['program_id', 'cycle_id', 'academic_year_id'],
        'metrics': ['total_applications', 'confirmed', 'admission_rate'],
        'time_col': None,
        'keywords': ('funnel', 'applicant', 'application', 'conversion',
                     'offer', 'shortlist', 'confirmed admission',
                     'admission rate', 'entrance score'),
    },
    'applicant_mix': {
        'label': 'Applicant Category Mix',
        'model': 'edicai.applicant.category.report',
        'table': 'edicai_applicant_category_report',
        'columns': ['academic_year_id', 'category', 'gender',
                    'total_applicants', 'confirmed', 'avg_score'],
        'dimensions': ['category', 'gender', 'academic_year_id'],
        'metrics': ['total_applicants', 'confirmed'],
        'time_col': None,
        'keywords': ('category', 'caste', 'quota', 'ews', 'obc', 'sc/st',
                     'gender mix', 'diversity'),
    },
    'fee_collection': {
        'label': 'Fee Collection',
        'model': 'edicai.fee.collection.report',
        'table': 'edicai_fee_collection_report',
        'columns': ['semester_id', 'invoice_state', 'invoice_count',
                    'total_billed', 'total_collected',
                    'total_outstanding', 'collection_rate'],
        'dimensions': ['semester_id', 'invoice_state'],
        'metrics': ['total_billed', 'total_collected',
                    'total_outstanding', 'collection_rate'],
        'time_col': None,
        'keywords': ('fee', 'collection', 'billed', 'outstanding',
                     'overdue', 'invoice', 'dues', 'receivable'),
    },
    'payment_methods': {
        'label': 'Payment Methods',
        'model': 'edicai.payment.method.report',
        'table': 'edicai_payment_method_report',
        'columns': ['payment_method', 'payment_month', 'payment_count',
                    'total_amount'],
        'dimensions': ['payment_method', 'payment_month'],
        'metrics': ['total_amount', 'payment_count'],
        'time_col': 'payment_month',
        'keywords': ('payment method', 'upi', 'cash', 'online payment',
                     'bank transfer', 'cheque', 'how paid', 'mode of pay'),
    },
    'finance_snapshot': {
        'label': 'Finance Daily Snapshot',
        'model': 'edicai.finance.snapshot',
        'table': 'edicai_finance_snapshot',
        'columns': ['snapshot_date', 'academic_year_id', 'semester_id',
                    'total_invoiced', 'total_collected',
                    'total_outstanding', 'total_overdue',
                    'collection_rate', 'invoice_count_total',
                    'invoice_count_paid', 'invoice_count_overdue',
                    'total_scholarship_awarded',
                    'scholarship_beneficiary_count', 'net_revenue'],
        'dimensions': ['semester_id', 'academic_year_id'],
        'metrics': ['total_collected', 'total_outstanding',
                    'net_revenue'],
        'time_col': 'snapshot_date',
        'keywords': ('snapshot', 'daily finance', 'net revenue',
                     'scholarship awarded', 'trend', 'financial position'),
    },
    'finance_kpi': {
        'label': 'Finance KPIs',
        'model': 'edicai.finance.kpi',
        'table': 'edicai_finance_kpi',
        'columns': ['kpi_date', 'semester_id', 'total_billed',
                    'total_collected', 'total_outstanding',
                    'collection_efficiency', 'total_students_billed',
                    'total_students_paid', 'total_students_overdue',
                    'total_students_scholarship', 'cash_collected',
                    'online_collected', 'bank_transfer_collected',
                    'other_collected'],
        'dimensions': ['semester_id'],
        'metrics': ['total_collected', 'collection_efficiency'],
        'time_col': 'kpi_date',
        'keywords': ('kpi', 'efficiency', 'students paid', 'cash vs',
                     'financial kpi', 'performance indicator'),
    },
}


def detect_intent(question):
    """Return the ALLOW_LIST key best matching *question* (or None)."""
    text = (question or '').lower()
    best, best_score = None, 0
    for key, entry in ALLOW_LIST.items():
        score = sum(1 for kw in entry['keywords'] if kw in text)
        if score > best_score:
            best, best_score = key, score
    return best


def suggest_chart(entry, selected_columns):
    """Pick 'bar' | 'line' | 'table' from the selected columns."""
    selected = set(selected_columns or [])
    dims = [c for c in entry.get('dimensions', []) if c in selected]
    mets = [c for c in entry.get('metrics', []) if c in selected]
    time_col = entry.get('time_col')
    if time_col and time_col in selected and mets:
        return 'line'
    if dims and mets:
        return 'bar'
    return 'table'


def _quote_ident(name):
    if not _IDENTIFIER_RE.match(name or ''):
        raise UserError(_('Invalid identifier: %s') % name)
    return '"%s"' % name


def plan_query(question=None, intent=None, columns=None, filters=None,
               order_by=None, limit=DEFAULT_LIMIT, company_id=None):
    """Build a read-only parameterized SELECT for an allow-listed source.

    Never raises raw SQL from user input: only ``intent`` (resolved via
    keyword match or an exact ALLOW_LIST key), ``columns``/``order_by``
    (each must be in the intent's fixed column set) and scalar filter
    values flow in; values are always bound parameters.
    """
    key = intent if intent in ALLOW_LIST else detect_intent(question or '')
    if not key:
        raise UserError(_(
            'Sorry, I can only answer questions about: %s.'
            % ', '.join(e['label'] for e in ALLOW_LIST.values())))
    entry = ALLOW_LIST[key]

    wanted = list(columns or entry['columns'])
    for col in wanted:
        if col not in entry['columns']:
            raise UserError(_('Column "%s" is not available for %s.')
                            % (col, entry['label']))
    selected = [c for c in entry['columns'] if c in wanted] or \
        list(entry['columns'])

    try:
        capped = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    except (TypeError, ValueError):
        capped = DEFAULT_LIMIT

    where = ['"company_id" = %(company_id)s']
    sql_params = {'company_id': company_id}
    for col, value in (filters or {}).items():
        if col not in entry['columns'] or col == 'company_id':
            raise UserError(_('Filter on "%s" is not allowed.') % col)
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            placeholders = []
            for pos, item in enumerate(value):
                if isinstance(item, bool) or not isinstance(
                        item, (int, float, str)):
                    raise UserError(_('Invalid filter value.'))
                pname = 'f_%s_%d' % (col, pos)
                placeholders.append('%%(%s)s' % pname)
                sql_params[pname] = item
            where.append('%s IN (%s)'
                         % (_quote_ident(col), ', '.join(placeholders)))
        else:
            if isinstance(value, bool) or not isinstance(
                    value, (int, float, str)):
                raise UserError(_('Invalid filter value.'))
            where.append('%s = %%(f_%s)s'
                         % (_quote_ident(col), col))
            sql_params['f_%s' % col] = value

    order_clause = ''
    if order_by:
        if order_by.lstrip('-') not in entry['columns']:
            raise UserError(_('Cannot order by "%s".') % order_by)
        direction = 'DESC' if order_by.startswith('-') else 'ASC'
        order_clause = ' ORDER BY %s %s' % (
            _quote_ident(order_by.lstrip('-')), direction)

    sql = 'SELECT %s FROM %s WHERE %s%s LIMIT %d' % (
        ', '.join(_quote_ident(c) for c in selected),
        _quote_ident(entry['table']),
        ' AND '.join(where), order_clause, capped)

    if _FORBIDDEN_RE.search(sql):
        # Cannot happen for builder output; defense in depth.
        raise UserError(_('Generated query failed the read-only check.'))

    return {
        'intent': key,
        'label': entry['label'],
        'model': entry['model'],
        'table': entry['table'],
        'sql': sql,
        'params': sql_params,
        'columns': selected,
        'chart': suggest_chart(entry, selected),
        'limit': capped,
    }


class EdicaiAIAskData(models.AbstractModel):
    """Read-only NL analytics over the ALLOW_LIST sources."""

    _name = 'edicai.ai.ask.data'
    _description = 'AI Ask-Data (read-only analytics)'

    @api.model
    def describe_intents(self):
        """Return the allow-listed intents (labels + fixed columns)."""
        return [{
            'intent': key,
            'label': entry['label'],
            'model': entry['model'],
            'columns': list(entry['columns']),
        } for key, entry in ALLOW_LIST.items()]

    @api.model
    def plan_query(self, question=None, intent=None, columns=None,
                   filters=None, order_by=None, limit=DEFAULT_LIMIT):
        """Plan (no DB access): return the parameterized SELECT shape."""
        return plan_query(
            question=question, intent=intent, columns=columns,
            filters=filters, order_by=order_by, limit=limit,
            company_id=self.env.company.id)

    @api.model
    def run_intent(self, params=None):
        """Plan + execute a read-only query for the requester company.

        ``params``: ``{'question'|'intent', 'columns', 'filters',
        'order_by', 'limit'}``.  ``company_id`` is forced to the
        requester's company regardless of what the caller passed.
        """
        params = dict(params or {})
        company_id = self.env.company.id
        plan = plan_query(
            question=params.get('question', ''),
            intent=params.get('intent'),
            columns=params.get('columns'),
            filters=params.get('filters'),
            order_by=params.get('order_by'),
            limit=params.get('limit', DEFAULT_LIMIT),
            company_id=company_id)
        sql_params = dict(plan['params'])
        sql_params['company_id'] = company_id
        if _FORBIDDEN_RE.search(plan['sql']):
            raise UserError(_('Query blocked by the read-only check.'))
        self.env.cr.execute(plan['sql'], sql_params)
        cols = [d[0] for d in self.env.cr.description]
        rows = [dict(zip(cols, row)) for row in self.env.cr.fetchall()]
        _logger.info('Ask-Data: intent=%s company=%s rows=%d chart=%s',
                     plan['intent'], company_id, len(rows), plan['chart'])
        return {
            'intent': plan['intent'],
            'label': plan['label'],
            'sql': plan['sql'],
            'columns': plan['columns'],
            'rows': rows,
            'count': len(rows),
            'chart': plan['chart'],
        }
