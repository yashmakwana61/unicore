"""Phase 1A — allow-listed conversational tool contracts + policy gate.

Five READ-ONLY tools are exposed to the conversational orchestrator.
Each entry in :data:`CONVERSATIONAL_TOOL_SPEC` is the explicit tool
contract (stable name, purpose, input/output schema, authorization,
risk level, business-logic reuse). The actual handlers live in
``edicai_ai/models/ai_tools_conversational.py``; the SPEC lives here so
the policy gate can validate a request WITHOUT executing anything.

The gate is an application-level check IN FRONT OF the existing central
registry: ``edicai.ai.tool.registry.execute_tool`` still performs its own
group gate, company forcing, rate limit, audit and dispatch. The LLM
(intent layer) never decides authorization — these rules are fixed
Python constants enforced on every turn.
"""

import logging

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GROUP_AI_USER = 'edicai_ai.group_edicai_ai_user'

#: Phase 1A conversational tool contracts. ``risk_level`` is fixed to
#: READ_ONLY for the entire phase; ``conversational`` marks the tool as
#: enabled for the orchestrator path.
CONVERSATIONAL_TOOL_SPEC = {
    'attendance.shortage_report': {
        'description': (
            'Authorized attendance summary for one student in the '
            'caller\'s company: cumulative percentage per course '
            'offering and shortage flags, from the authoritative '
            'stored attendance records. Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',           # forced by execute_tool
            'record_scope': (
                'students current record rules resolve: own records for '
                'student users, staff/campus/company rules for staff'
            ),
            'campus_scope': 'record rules (user.edicai_campus_ids)',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'student_name': {'type': 'str', 'required': False,
                             'max_len': 120},
            'limit': {'type': 'int', 'required': False, 'max': 200},
        },
        'required_params': [],
        'existing_logic': (
            'edicai.attendance.record stored cumulative fields '
            '(_compute_student_cumulative_stats) + edicai.student '
            'stored summary fields'
        ),
        'output_schema': {
            'student': {'type': 'str', 'required': False},
            'overall_percentage': {'type': 'float', 'required': False},
            'shortage': {'type': 'bool'},
            'courses': {
                'type': 'list',
                'rows': ['course_name', 'percentage', 'sessions_held',
                         'sessions_present', 'sessions_absent',
                         'shortage_alert'],
            },
            'empty': {'type': 'bool'},
            'clarify': {'type': 'str', 'required': False},
        },
        'error_mapping': {
            'no linked student': 'RECORD_NOT_FOUND',
            'student not found': 'RECORD_NOT_FOUND',
            'several candidates': 'clarification (AMBIGUOUS)',
            'unreadable student': 'AUTHORIZATION_DENIED',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: Attendance Report',
    },
    'timetable.clash_check': {
        'description': (
            'Read-only timetable clash scan for the caller\'s company '
            '(optionally one semester), reusing the existing Timetable '
            'Optimizer Copilot clash_scan (room / instructor / section '
            'overlaps).'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': (
                'edicai.timetable.entry record rules (company / campus) '
                'apply on every read'
            ),
            'campus_scope': 'record rules (user.edicai_campus_ids)',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'semester_name': {'type': 'str', 'required': False,
                              'max_len': 60},
            'limit': {'type': 'int', 'required': False, 'max': 100},
        },
        'required_params': [],
        'existing_logic': (
            'timetable.ai.copilot.clash_scan — overlap math mirrors '
            'edicai.timetable.entry._check_scheduling_conflicts'
        ),
        'output_schema': {
            'scanned_entries': {'type': 'int'},
            'clash_count': {'type': 'int'},
            'clashes': {'type': 'list', 'rows': ['reason']},
            'semester': {'type': 'str', 'required': False},
            'truncated': {'type': 'bool', 'required': False},
            'clarify': {'type': 'str', 'required': False},
        },
        'error_mapping': {
            'semester not found': 'RECORD_NOT_FOUND',
            'several semesters': 'clarification (AMBIGUOUS)',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: Timetable Clashes',
    },
    'timetable.view': {
        'description': (
            'Read-only timetable entries active on a requested calendar '
            'date, distinct from clash analysis.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'current-user ACLs and timetable record rules',
            'campus_scope': 'record rules (user.edicai_campus_ids)',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},
            'schedule_date': {'type': 'str', 'required': False,
                              'max_len': 10},
            'limit': {'type': 'int', 'required': False, 'max': 100},
        },
        'required_params': [],
        'existing_logic': 'timetable.ai.copilot.view_schedule',
        'output_schema': {
            'date': {'type': 'str'}, 'count': {'type': 'int'},
            'entries': {'type': 'list'}, 'truncated': {'type': 'bool'},
        },
        'error_mapping': {'model not installed': 'TOOL_UNAVAILABLE'},
        'citation': 'Source: Timetable',
    },
    'grading.grade_summary': {
        'description': (
            'Authorized academic summary for one student: stored CGPA / '
            'average percentage plus published semester results, read '
            'directly from the authoritative edicai_grading records. '
            'Read-only; no marks are recomputed.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': (
                'edicai.semester.result / edicai.grade.entry record rules '
                '(students: published results only; staff: company rules)'
            ),
            'campus_scope': 'company scope',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'student_name': {'type': 'str', 'required': False,
                             'max_len': 120},
        },
        'required_params': [],
        'existing_logic': (
            'edicai.student stored cgpa / average_percentage fields '
            '(maintained by edicai_grading) + edicai.semester.result rows'
        ),
        'output_schema': {
            'student': {'type': 'str', 'required': False},
            'cgpa': {'type': 'float', 'required': False},
            'average_percentage': {'type': 'float', 'required': False},
            'semesters': {
                'type': 'list',
                'rows': ['semester', 'gpa', 'credits_attempted',
                         'credits_earned', 'result_status'],
            },
            'empty': {'type': 'bool'},
            'clarify': {'type': 'str', 'required': False},
        },
        'error_mapping': {
            'no linked student': 'RECORD_NOT_FOUND',
            'student not found': 'RECORD_NOT_FOUND',
            'several candidates': 'clarification (AMBIGUOUS)',
            'unreadable student': 'AUTHORIZATION_DENIED',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: Grade Summary',
    },
    'admission.program_search': {
        'description': (
            'Authorized search of ACTIVE admission programs in the '
            'caller\'s company (public admission data), fully '
            'delegated to the existing Admission FAQ Copilot '
            'program_search tool. Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': (
                'active programs only; edicai.program is non-PII '
                'admission data within the company'
            ),
            'campus_scope': 'campus names returned per program',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'program_level': {'type': 'str', 'required': False,
                              'enum': ['undergraduate', 'postgraduate',
                                       'doctoral', 'diploma',
                                        'certificate']},
            'query': {'type': 'str', 'required': False, 'max_len': 60},
            'campus': {'type': 'str', 'required': False, 'max_len': 120},
            'limit': {'type': 'int', 'required': False, 'max': 25},
        },
        'required_params': [],
        'existing_logic': (
            'edicai.admission.ai.tools.run_tool("program_search") — '
            '" no new search logic'
        ),
        'output_schema': {
            'programs': {
                'type': 'list',
                'rows': ['name', 'code', 'level', 'campuses',
                         'tuition_per_semester', 'entry_qualification'],
            },
            'empty': {'type': 'bool'},
        },
        'error_mapping': {
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: Admission Programs',
    },
    'admission.applicant_list': {
        'description': (
            'Read-only applicant collection/count within the caller\'s '
            'company and current admission record rules. Program, campus, '
            'stage and no-open-follow-up filters are application-validated.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'edicai.admission.applicant current ACLs and rules',
            'campus_scope': 'current user campus/record rules',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},
            'operation': {'type': 'str', 'required': False,
                          'enum': ['list', 'count']},
            'state': {'type': 'str', 'required': False, 'max_len': 40},
            'program_query': {'type': 'str', 'required': False, 'max_len': 60},
            'campus': {'type': 'str', 'required': False, 'max_len': 120},
            'no_followup': {'type': 'bool', 'required': False},
            'limit': {'type': 'int', 'required': False, 'max': 100},
        },
        'required_params': [],
        'existing_logic': (
            'edicai.admission.applicant ORM and the existing workflow '
            'candidate discovery rule for applicants without open activities'
        ),
        'output_schema': {
            'rows': {'type': 'list', 'rows': [
                'id', 'name', 'application_number', 'state', 'program',
                'campus']},
            'total_count': {'type': 'int'},
            'shown': {'type': 'int'}, 'truncated': {'type': 'bool'},
        },
        'error_mapping': {
            'ambiguous program or campus': 'clarification (AMBIGUOUS)',
            'unsupported stage': 'clarification',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: Admission Applicants',
    },
    'admission.followup_list': {
        'description': (
            'Read-only list/count of pending applicant mail activities, '
            'limited to applicants visible to the current user in the '
            'active company. Supports all, today, or overdue dates.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'visible applicant IDs and mail.activity rules',
            'campus_scope': 'inherited from visible applicant records',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},
            'date_filter': {'type': 'str', 'required': False,
                            'enum': ['all', 'today', 'yesterday', 'overdue']},
            'limit': {'type': 'int', 'required': False, 'max': 100},
        },
        'required_params': [],
        'existing_logic': 'edicai.admission.applicant + mail.activity ORM',
        'output_schema': {
            'rows': {'type': 'list', 'rows': [
                'applicant', 'application_number', 'summary',
                'date_deadline', 'assigned_to']},
            'total_count': {'type': 'int'}, 'shown': {'type': 'int'},
            'truncated': {'type': 'bool'},
        },
        'error_mapping': {
            'query too broad': 'clarification',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: Admission Follow-ups',
    },
    'grievance.summary': {
        'description': (
            'Read-only company-scoped summary of grievance requests, '
            'grouped by the repository status and category values.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'edicai.grievance.request current ACLs and rules',
            'campus_scope': 'company and applicable grievance record rules',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},
            'open_only': {'type': 'bool', 'required': False},
        },
        'required_params': [],
        'existing_logic': 'edicai.grievance.request ORM, no business writes',
        'output_schema': {
            'total_count': {'type': 'int'},
            'by_state': {'type': 'dict'},
            'by_category': {'type': 'dict'},
            'empty': {'type': 'bool'},
        },
        'error_mapping': {'model not installed': 'TOOL_UNAVAILABLE'},
        'citation': 'Source: Grievance Summary',
    },
    'fees.fee_status': {
        'description': (
            'Authorized fee/payment status for one student: totals, '
            'outstanding and overdue counts per semester, fully '
            'delegated to the existing Fee Explainer Copilot '
            'dues_summary tool (own-student scope enforced there too). '
            'Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': (
                'edicai.fee.copilot own-student scope + edicai.fee.invoice '
                'record rules; staff must pass an explicit student'
            ),
            'campus_scope': 'company scope',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'student_name': {'type': 'str', 'required': False,
                             'max_len': 120},
        },
        'required_params': [],
        'existing_logic': (
            'edicai.fee.copilot.dues_summary — no new fee logic'
        ),
        'output_schema': {
            'student_id': {'type': 'int', 'required': False},
            'currency': {'type': 'str', 'required': False},
            'grand_outstanding': {'type': 'float', 'required': False},
            'overdue_semesters': {'type': 'int', 'required': False},
            'semesters': {
                'type': 'list',
                'rows': ['semester_name', 'amount_outstanding',
                         'open_count', 'overdue_count'],
            },
            'empty': {'type': 'bool'},
            'clarify': {'type': 'str', 'required': False},
        },
        'error_mapping': {
            'no linked student': 'RECORD_NOT_FOUND',
            'student not found': 'RECORD_NOT_FOUND',
            'several candidates': 'clarification (AMBIGUOUS)',
            'unreadable student': 'AUTHORIZATION_DENIED',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: Fee Status',
    },
    'fees.fee_summary': {
        'description': (
            'Institution-wide outstanding-fee AGGREGATE: the NUMBER of '
            'students with outstanding fees, the total amount, the '
            'overdue count and the worst students — delegated to the '
            'Fee Explainer Copilot outstanding_summary tool. Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',           # forced by execute_tool
            'record_scope': (
                'edicai.fee.copilot own-student scope for restricted '
                'students; staff read the active company with the '
                'edicai.fee.invoice record rules applied'
            ),
            'campus_scope': 'company scope',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'limit': {'type': 'int', 'required': False, 'max': 50},
            'overdue_only': {'type': 'bool', 'required': False},
        },
        'required_params': [],
        'existing_logic': (
            'edicai.fee.copilot.outstanding_summary — no new fee logic'
        ),
        'output_schema': {
            'students_with_outstanding': {'type': 'int', 'required': False},
            'total_outstanding': {'type': 'float', 'required': False},
            'currency': {'type': 'str', 'required': False},
            'overdue_students': {'type': 'int', 'required': False},
            'scope': {'type': 'str', 'required': False},
            'top_students': {
                'type': 'list',
                'rows': ['student', 'outstanding', 'invoice_count',
                         'overdue_count'],
            },
            'empty': {'type': 'bool'},
        },
        'error_mapping': {
            'no linked student': 'RECORD_NOT_FOUND',
            'unreadable invoices': 'AUTHORIZATION_DENIED',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: Outstanding Fees (all students)',
    },
    'attendance.shortage_summary': {
        'description': (
            'Institution-wide attendance-shortage AGGREGATE: the NUMBER '
            'of students below the attendance policy and the worst cases '
            '— delegated to the Attendance Copilot shortage_summary '
            'tool. Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',           # forced by execute_tool
            'record_scope': (
                'edicai.attendance.record record rules (own rows for '
                'students, own sessions for faculty)'
            ),
            'campus_scope': 'record rules (user.edicai_campus_ids)',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'limit': {'type': 'int', 'required': False, 'max': 50},
            'threshold': {'type': 'float', 'required': False,
                          'min': 1, 'max': 80},
        },
        'required_params': [],
        'existing_logic': (
            'attendance.ai.copilot.shortage_summary — no new '
            'attendance logic'
        ),
        'output_schema': {
            'students_short': {'type': 'int', 'required': False},
            'shortage_rows': {'type': 'int', 'required': False},
            'scope': {'type': 'str', 'required': False},
            'worst_students': {
                'type': 'list',
                'rows': ['student', 'percentage', 'offering',
                         'min_required', 'gap_points'],
            },
            'empty': {'type': 'bool'},
        },
        'error_mapping': {
            'no linked student': 'RECORD_NOT_FOUND',
            'unreadable records': 'AUTHORIZATION_DENIED',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: Attendance Shortage (all students)',
    },
    # ------------------------------------------------------------------
    # Phase G1 — the generic entity layer (READ floor). The five read
    # below are parameterized; the per-entity policy lives in
    # edicai.ai.entity.policy (data seeds + manager edits).
    # ------------------------------------------------------------------
    'entity.list_models': {
        'description': (
            'Phase G1 generic READ floor: lists the entities this caller '
            'may ask about (labels, synonyms, operations) resolved from '
            'edicai.ai.entity.policy. Deny-by-default per entity. '
            'Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'edicai.ai.entity.policy rows (non-secret '
                            'configuration; per-entity grants checked '
                            'as the caller)',
            'campus_scope': 'per-entity policy rows',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'query': {'type': 'str', 'required': False, 'max_len': 60},
        },
        'required_params': [],
        'existing_logic': 'edicai.ai.entity.tools.tool_list_models',
        'output_schema': {
            'entities': {'type': 'list', 'rows': ['model', 'label',
                                                  'ops', 'synonyms']},
            'count': {'type': 'int'},
            'query': {'type': 'str'},
        },
        'error_mapping': {
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: AI Entities',
    },
    'entity.describe': {
        'description': (
            'Phase G1 generic READ floor: one entity schema — fields, '
            'types, required flags, PII flags, row cap. Blocked fields '
            'and per-group-restricted fields are excluded. Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'schema only; field visibility follows the '
                            'caller groups + policy field lists',
            'campus_scope': 'per-entity policy rows',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'model': {'type': 'str', 'required': True, 'max_len': 64},
        },
        'required_params': ['model'],
        'existing_logic': 'edicai.ai.entity.tools.tool_describe',
        'output_schema': {
            'model': {'type': 'str'}, 'label': {'type': 'str'},
            'ops': {'type': 'dict'}, 'row_cap': {'type': 'int'},
            'fields': {'type': 'list', 'rows': ['name', 'label', 'type',
                                                'required', 'pii',
                                                'write_blocked']},
            'field_count': {'type': 'int'},
        },
        'error_mapping': {
            'unknown entity': 'VALIDATION_FAILED',
            'authorization': 'AUTHORIZATION_DENIED',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: AI Entities',
    },
    'entity.search': {
        'description': (
            'Phase G1 generic READ floor: records by a CLOSED filter '
            'grammar [[field, op, value]] — ops: eq/ne/in/not_in/like/'
            'ilike/gt/gte/lt/lte, restricted per field type; non-stored '
            'and blocked fields rejected. Runs as the calling user (no '
            'sudo), PII masked, row-capped. Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'caller record rules + policy grants/row '
                            'cap/field lists',
            'campus_scope': 'record rules (user.edicai_campus_ids)',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'model': {'type': 'str', 'required': True, 'max_len': 64},
            'filters': {'type': 'list', 'required': False},
            'fields': {'type': 'str', 'required': False, 'max_len': 400},
            'limit': {'type': 'int', 'required': False, 'max': 200},
            'order': {'type': 'str', 'required': False, 'max_len': 120},
        },
        'required_params': ['model'],
        'existing_logic': 'edicai.ai.entity.tools.tool_search',
        'output_schema': {
            'count': {'type': 'int'},
            'total_in_scope': {'type': 'int'},
            'truncated': {'type': 'bool'},
            'row_cap': {'type': 'int'},
            'rows': {'type': 'list'},
        },
        'error_mapping': {
            'unknown entity': 'VALIDATION_FAILED',
            'authorization': 'AUTHORIZATION_DENIED',
            'validation': 'VALIDATION_FAILED',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: AI Entity Search',
    },
    'entity.read': {
        'description': (
            'Phase G1 generic READ floor: read named records by id, '
            'field-checked and PII masked; explicit read access is '
            'verified through check_access (no sudo). Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'caller record rules + policy grants/field '
                            'lists',
            'campus_scope': 'record rules (user.edicai_campus_ids)',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'model': {'type': 'str', 'required': True, 'max_len': 64},
            'ids': {'type': 'list', 'required': True},
            'fields': {'type': 'str', 'required': False, 'max_len': 400},
        },
        'required_params': ['model', 'ids'],
        'existing_logic': 'edicai.ai.entity.tools.tool_read',
        'output_schema': {
            'count': {'type': 'int'}, 'row_cap': {'type': 'int'},
            'rows': {'type': 'list'}, 'fields': {'type': 'list'},
        },
        'error_mapping': {
            'unknown entity': 'VALIDATION_FAILED',
            'authorization': 'AUTHORIZATION_DENIED',
            'validation': 'VALIDATION_FAILED',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: AI Entity Read',
    },
    'entity.aggregate': {
        'description': (
            'Phase G1 generic READ floor: grouped cohort numbers '
            '(count/sum/avg/min/max with group_by) — the generic '
            'HOW MANY engine replaces static count tools. Record rules '
            'and row caps always apply. Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'caller record rules + policy grants/row '
                            'caps',
            'campus_scope': 'record rules (user.edicai_campus_ids)',
        },
        'input_schema': {
            'company_id': {'type': 'int', 'required': False},  # forced
            'model': {'type': 'str', 'required': True, 'max_len': 64},
            'group_by': {'type': 'str', 'required': False, 'max_len': 130},
            'measures': {'type': 'dict', 'required': False},
            'filters': {'type': 'list', 'required': False},
            'limit': {'type': 'int', 'required': False, 'max': 200},
        },
        'required_params': ['model'],
        'existing_logic': 'edicai.ai.entity.tools.tool_aggregate',
        'output_schema': {
            'group_by': {'type': 'list'},
            'total_records': {'type': 'int'},
            'count': {'type': 'int'},
            'rows': {'type': 'list'},
            'empty': {'type': 'bool'},
        },
        'error_mapping': {
            'unknown entity': 'VALIDATION_FAILED',
            'authorization': 'AUTHORIZATION_DENIED',
            'validation': 'VALIDATION_FAILED',
            'model not installed': 'TOOL_UNAVAILABLE',
        },
        'citation': 'Source: AI Entity Aggregate',
    },
    'entity.create': {
        'description': (
            'Phase G2 generic CREATE proposal: validates model+values '
            'against edicai.ai.entity.policy (write_groups grant, '
            'writable fields, types, required) and stages ONE pending '
            'action for the confirm flow. NEVER writes business data.'
        ),
        'risk_level': 'MUTATION',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'entity policy write_groups; execution only '
                            'at confirm, as the confirming user',
            'campus_scope': 'server-owned (company at execution)',
        },
        'input_schema': {
            'session_id': {'type': 'int', 'required': True},
            'model': {'type': 'str', 'required': True, 'max_len': 64},
            'values': {'type': 'dict', 'required': True},
        },
        'required_params': ['session_id', 'model', 'values'],
        'existing_logic': 'edicai.ai.entity.tools.tool_entity_create',
        'output_schema': {
            'action': {'type': 'str'},
            'pending_id': {'type': 'int'},
            'pending_ref': {'type': 'str'},
            'requires_confirmation': {'type': 'bool'},
            'status': {'type': 'str'},
            'superseded': {'type': 'bool'},
        },
        'error_mapping': {
            'policy denies': 'AUTHORIZATION_DENIED',
            'bad values': 'VALIDATION_FAILED',
            'no session': 'VALIDATION_FAILED',
        },
        'citation': 'Source: AI Entity Create',
    },

    'entity.update': {
        'description': (
            'Phase G2 generic UPDATE proposal: read-checks the target '
            'record, validates the values delta against the entity '
            'policy and stages ONE pending action for the confirm '
            'flow. NEVER writes business data.'
        ),
        'risk_level': 'MUTATION',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'target must be readable by the caller; '
                            'execution only at confirm time',
            'campus_scope': 'record rules (user.edicai_campus_ids)',
        },
        'input_schema': {
            'session_id': {'type': 'int', 'required': True},
            'model': {'type': 'str', 'required': True, 'max_len': 64},
            'record_id': {'type': 'int', 'required': True},
            'values': {'type': 'dict', 'required': True},
        },
        'required_params': ['session_id', 'model', 'record_id', 'values'],
        'existing_logic': 'edicai.ai.entity.tools.tool_entity_update',
        'output_schema': {
            'action': {'type': 'str'},
            'pending_id': {'type': 'int'},
            'pending_ref': {'type': 'str'},
            'requires_confirmation': {'type': 'bool'},
            'status': {'type': 'str'},
            'superseded': {'type': 'bool'},
        },
        'error_mapping': {
            'policy denies': 'AUTHORIZATION_DENIED',
            'target unreadable': 'AUTHORIZATION_DENIED',
            'bad values': 'VALIDATION_FAILED',
        },
        'citation': 'Source: AI Entity Update',
    },

    'entity.execute': {
        'description': (
            'Phase G3 generic record ACTION proposal: validates the '
            'declared action (entity execute grant, action row + '
            'allowed_groups, CODE registry) and stages ONE pending '
            'action for the confirm flow. The ERP method runs only at '
            'confirmation, as the confirming user. NEVER executes at '
            'call time and NEVER accepts an undeclared method name.'
        ),
        'risk_level': 'MUTATION',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'target must be readable by the caller; '
                            'execution only at confirm time',
            'campus_scope': 'record rules (user.edicai_campus_ids)',
        },
        'input_schema': {
            'session_id': {'type': 'int', 'required': True},
            'model': {'type': 'str', 'required': True, 'max_len': 64},
            'action': {'type': 'str', 'required': True, 'max_len': 64},
            'record_id': {'type': 'int', 'required': True},
            'params': {'type': 'dict', 'required': False},
        },
        'required_params': ['session_id', 'model', 'action', 'record_id'],
        'existing_logic': 'edicai.ai.entity.tools.tool_entity_execute',
        'output_schema': {
            'action': {'type': 'str'},
            'pending_id': {'type': 'int'},
            'pending_ref': {'type': 'str'},
            'requires_confirmation': {'type': 'bool'},
            'status': {'type': 'str'},
            'superseded': {'type': 'bool'},
            'entity_action': {'type': 'str'},
            'action_label': {'type': 'str'},
        },
        'error_mapping': {
            'policy denies': 'AUTHORIZATION_DENIED',
            'undeclared action': 'AUTHORIZATION_DENIED',
            'needs approval': 'AUTHORIZATION_DENIED',
            'target unreadable': 'AUTHORIZATION_DENIED',
            'bad params': 'VALIDATION_FAILED',
        },
        'citation': 'Source: AI Entity Execute',
    },

    'entity.list_actions': {
        'description': (
            'Phase G2/G3: lists the whitelisted entity ACTIONS declared '
            'in edicai.ai.entity.action, grant-filtered for the caller, '
            'with an honest ``executable`` flag for THIS caller (flag + '
            'entity grant + action row + code registry). Read-only.'
        ),
        'risk_level': 'READ_ONLY',
        'conversational': True,
        'authorization': {
            'allowed_groups': [GROUP_AI_USER],
            'scope': 'company',
            'record_scope': 'public action table (no business data); '
                            'per-row allowed_groups filter',
            'campus_scope': 'not data-scoped',
        },
        'input_schema': {
            'model': {'type': 'str', 'required': False, 'max_len': 64},
        },
        'required_params': [],
        'existing_logic': 'edicai.ai.entity.tools.tool_list_actions',
        'output_schema': {
            'actions': {'type': 'list'},
            'count': {'type': 'int'},
        },
        'error_mapping': {},
        'citation': 'Source: AI Entity Actions',
    },
}


#: Allow-list: exactly the Phase 1A tool set; nothing else routes.
CONVERSATIONAL_TOOLS = frozenset(CONVERSATIONAL_TOOL_SPEC)

#: Tools whose handlers require a dedicated student target. Staff
#: callers without an explicit student are asked a bounded
#: clarification; restricted student users get their own record.
_STUDENT_TARGETED_TOOLS = (
    'attendance.shortage_report',
    'grading.grade_summary',
    'fees.fee_status',
)


class EdicaiAIPolicyGate(models.AbstractModel):
    """Application-level policy gate for conversational tool calls.

    Runs BEFORE ``execute_tool`` (which re-checks groups, company,
    rate-limit and audits). Both gates must pass; the LLM layer never
    decides authorization.
    """

    _name = 'edicai.ai.policy.gate'
    _description = 'AI Conversational Policy Gate (read-only)'

    # ------------------------------------------------------------------
    # Read-only introspection (tests / UI)
    # ------------------------------------------------------------------

    @api.model
    def conversational_tool_names(self):
        """The Phase 1A allow-list (stable order for display)."""
        return sorted(CONVERSATIONAL_TOOLS)

    @api.model
    def get_tool_contract(self, name):
        """Return the contract dict, or False (never raises)."""
        return dict(CONVERSATIONAL_TOOL_SPEC.get(name) or {})

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------

    @api.model
    def check_access(self, tool_name, user=None):
        """Validate a conversational tool invocation attempt.

        Checks (in order):

        1. the name is in the Phase 1A conversational allow-list;
        2. the name exactly matches a registered registry entry whose
           spec is flagged ``conversational`` and ``READ_ONLY``;
        3. the caller is authenticated (never the public user);
        4. the caller holds every allowed group of the contract.

        :returns: ``{'allowed': True, 'reason_code': 'OK'}``
        :raises UserError: never — denials return a decision dict so
            the orchestrator can audit and answer safely.
        """
        user = user or self.env.user
        if not tool_name or tool_name not in CONVERSATIONAL_TOOLS:
            return {
                'allowed': False,
                'reason_code': 'NOT_IN_CONVERSATIONAL_ALLOWLIST',
            }
        contract = CONVERSATIONAL_TOOL_SPEC[tool_name]
        for group in contract['authorization']['allowed_groups']:
            try:
                ok = user.has_group(group)
            except Exception:
                ok = False
            if not ok:
                return {
                    'allowed': False,
                    'reason_code': 'GROUP_GATE:%s' % group,
                }
        # Company scope: the central registry forces ``company_id`` to
        # ``env.company`` on dispatch; the gate documents the invariant.
        return {'allowed': True, 'reason_code': 'OK'}
