# -*- coding: utf-8 -*-
"""Reversible navigation preview engine (Stage D).

Authoritative mapping source: docs/navigation_audit/menu_migration_manifest.csv.
39 reparent rows are embedded below; each row is validated against the live
database before any write. Original parent/sequence are snapshotted to
ir.config_parameter so disable restores the exact prior state.
"""
import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

PARAM_STATE = 'edicai_navigation.preview_state'
PARAM_SNAPSHOT = 'edicai_navigation.preview_snapshot'

WORKSPACE_XMLIDS = [
    'edicai_navigation.menu_workspace_10',
    'edicai_navigation.menu_workspace_20',
    'edicai_navigation.menu_workspace_30',
    'edicai_navigation.menu_workspace_40',
    'edicai_navigation.menu_workspace_50',
    'edicai_navigation.menu_workspace_60',
    'edicai_navigation.menu_workspace_70',
    'edicai_navigation.menu_workspace_80',
    'edicai_navigation.menu_workspace_90',
    'edicai_navigation.menu_workspace_100',
    'edicai_navigation.menu_workspace_110',
]

# (menu_xmlid, destination_parent_xmlid, new_sequence)
MANIFEST_REPARENTS = [
    ('edicai_admission.menu_edicai_admission_root', 'edicai_navigation.menu_workspace_20', 20),
    ('edicai_lms.menu_edicai_lms_root', 'edicai_navigation.menu_workspace_40', 40),
    ('edicai_analytics.menu_edicai_analytics_root', 'edicai_navigation.menu_workspace_90', 90),
    ('edicai_appointment.menu_edicai_appointment_root', 'edicai_navigation.menu_workspace_100', 100),
    ('edicai_asset_request.menu_edicai_asset_request_root', 'edicai_navigation.menu_workspace_70', 70),
    ('edicai_assignment.menu_edicai_assignment', 'edicai_navigation.menu_workspace_40', 40),
    ('edicai_attendance.menu_edicai_attendance', 'edicai_navigation.menu_workspace_30', 30),
    ('edicai_digital_library.menu_edicai_digital_library_root', 'edicai_navigation.menu_workspace_70', 70),
    ('edicai_discipline.menu_edicai_discipline_root', 'edicai_navigation.menu_workspace_30', 30),
    ('edicai_documents.menu_edicai_documents_root', 'edicai_navigation.menu_workspace_100', 100),
    ('edicai_ai.menu_edicai_ai_root', 'edicai_navigation.menu_workspace_100', 100),
    ('edicai_exam.menu_edicai_exam', 'edicai_navigation.menu_workspace_50', 50),
    ('edicai_fees.menu_edicai_fees_root', 'edicai_navigation.menu_workspace_60', 60),
    ('edicai_finance_report.menu_edicai_finance_report_root', 'edicai_navigation.menu_workspace_90', 90),
    ('edicai_grading.menu_edicai_grading', 'edicai_navigation.menu_workspace_50', 50),
    ('edicai_grievance.menu_edicai_grievance_root', 'edicai_navigation.menu_workspace_30', 30),
    ('edicai_hostel.menu_edicai_hostel_root', 'edicai_navigation.menu_workspace_70', 70),
    ('edicai_library.menu_edicai_library_root', 'edicai_navigation.menu_workspace_70', 70),
    ('edicai_mentor.menu_edicai_mentor_root', 'edicai_navigation.menu_workspace_30', 30),
    ('edicai_notice_board.menu_edicai_notice_root', 'edicai_navigation.menu_workspace_100', 100),
    ('edicai_notify.menu_edicai_notify_root', 'edicai_navigation.menu_workspace_100', 100),
    ('edicai_placement.menu_edicai_placement_root', 'edicai_navigation.menu_workspace_80', 80),
    ('edicai_progression.menu_edicai_progression_root', 'edicai_navigation.menu_workspace_30', 30),
    ('edicai_quiz.menu_edicai_quiz_root', 'edicai_navigation.menu_workspace_40', 40),
    ('edicai_scholarship.menu_edicai_scholarship_root', 'edicai_navigation.menu_workspace_60', 60),
    ('edicai_secure_transcript.menu_edicai_secure_transcript_root', 'edicai_navigation.menu_workspace_30', 30),
    ('edicai_skill_assessment.menu_edicai_skill_root', 'edicai_navigation.menu_workspace_80', 80),
    ('edicai_thesis.menu_edicai_thesis_root', 'edicai_navigation.menu_workspace_80', 80),
    ('edicai_timetable.menu_edicai_timetable', 'edicai_navigation.menu_workspace_50', 50),
    ('edicai_transport.menu_edicai_transport_root', 'edicai_navigation.menu_workspace_70', 70),
    ('edicai_base.menu_edicai_overview', 'edicai_navigation.menu_workspace_10', 1),
    ('edicai_base.menu_edicai_campuses', 'edicai_navigation.menu_workspace_10', 5),
    ('edicai_base.menu_edicai_configuration', 'edicai_navigation.menu_workspace_10', 999),
    ('edicai_academic.menu_edicai_academic', 'edicai_navigation.menu_workspace_10', 10),
    ('edicai_calendar.menu_edicai_calendar', 'edicai_navigation.menu_workspace_10', 20),
    ('edicai_student.menu_edicai_student_root', 'edicai_navigation.menu_workspace_30', 50),
    ('edicai_faculty_profile.menu_edicai_faculty_staff', 'edicai_navigation.menu_workspace_10', 40),
    ('edicai_curriculum.menu_edicai_curriculum', 'edicai_navigation.menu_workspace_10', 50),
    ('edicai_api.menu_edicai_api_root', 'edicai_navigation.menu_workspace_110', 90),
]


class NavigationPreviewUtil(models.AbstractModel):
    _name = 'navigation.preview.util'
    _description = 'Navigation Preview Engine (toggle logic, sudo-only)'

    @api.model
    def _state(self):
        return self.env['ir.config_parameter'].sudo().get_param(PARAM_STATE, 'off')

    @api.model
    def _snapshot_param(self):
        return self.env['ir.config_parameter'].sudo().get_param(PARAM_SNAPSHOT, '')

    @api.model
    def _validate_missing(self):
        """Return dict of xmlids that do not currently resolve in this DB."""
        missing = {}
        for xmlid, _dest, _seq in MANIFEST_REPARENTS:
            if not self.env.ref(xmlid, raise_if_not_found=False):
                missing.setdefault('menu', []).append(xmlid)
        for xid in WORKSPACE_XMLIDS:
            if not self.env.ref(xid, raise_if_not_found=False):
                missing.setdefault('workspace', []).append(xid)
        for _xmlid, dest, _seq in MANIFEST_REPARENTS:
            if not self.env.ref(dest, raise_if_not_found=False):
                missing.setdefault('workspace', []).append(dest)
        return missing

    @api.model
    def _xmlid_of(self, menu):
        data = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.ui.menu'), ('res_id', '=', menu.id)], limit=1)
        return ('%s.%s' % (data.module, data.name)) if data else ''

    @api.model
    def enable_preview(self):
        if self._state() == 'on':
            return {'ok': False, 'error': 'Preview is already enabled.'}
        missing = self._validate_missing()
        if missing:
            return {'ok': False, 'error': 'Refusing: unresolved XML IDs %s' % missing}
        icp = self.env['ir.config_parameter'].sudo()
        snapshot = {}
        for xmlid, dest, new_seq in MANIFEST_REPARENTS:
            menu = self.env.ref(xmlid).sudo()
            snapshot[xmlid] = {
                'parent_xmlid': (self._xmlid_of(menu.parent_id)
                                 if menu.parent_id else ''),
                'sequence': menu.sequence,
            }
            menu.parent_id = self.env.ref(dest).sudo().id
            menu.sequence = int(new_seq)
        for xid in WORKSPACE_XMLIDS:
            root = self.env.ref(xid).sudo()
            root.active = True
            if not root.sequence or root.sequence == 0:
                root.sequence = 1000
        icp.set_param(PARAM_SNAPSHOT, json.dumps(snapshot, sort_keys=True))
        icp.set_param(PARAM_STATE, 'on')
        _logger.info('Edicai navigation preview ENABLED (%s menus reparented).',
                     len(MANIFEST_REPARENTS))
        return {'ok': True, 'changed': len(MANIFEST_REPARENTS)}

    @api.model
    def disable_preview(self):
        if self._state() != 'on':
            return {'ok': False, 'error': 'Preview is not enabled.'}
        raw = self._snapshot_param()
        if not raw:
            return {'ok': False, 'error':
                    'Refusing: no snapshot found; restore from the pre-migration '
                    'inventory instead.'}
        snapshot = json.loads(raw)
        for xmlid, snap in snapshot.items():
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if not menu:
                _logger.warning('Snapshot menu missing, skipping: %s', xmlid)
                continue
            parent = None
            if snap.get('parent_xmlid'):
                parent = self.env.ref(snap['parent_xmlid'], raise_if_not_found=False)
            menu.parent_id = parent.id if parent else None
            menu.sequence = int(snap.get('sequence') or 0)
        for xid in WORKSPACE_XMLIDS:
            root = self.env.ref(xid, raise_if_not_found=False)
            if root:
                root.sudo().active = False
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(PARAM_STATE, 'off')
        _logger.info('Edicai navigation preview DISABLED (restored %s menus).',
                     len(snapshot))
        return {'ok': True, 'restored': len(snapshot)}
