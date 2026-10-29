# -*- coding: utf-8 -*-
{
    'name': 'Edicai Navigation Preview',
    'version': '19.0.1.1.0',
    'category': 'Education/Navigation',
    'summary': 'Reversible workspace navigation preview (custom + standard apps)',
    'description': """
Stage D of the navigation restructuring — combined custom + standard edition:
- 11 workspace roots ship INACTIVE (invisible while the preview state is off).
- An admin-only wizard enables the preview: 39 custom menus + 12 standard
  Odoo app roots are reparented into workspaces exactly as recorded in
  docs/navigation_audit/menu_migration_manifest.csv. A JSON snapshot of every
  original parent/sequence is persisted so disabling restores the original
  layout without data loss.
- Enable/disable is per database (menu structure is server-side in ir.ui.menu):
  run this module on an isolated staging/demo database per the approved plan.
- Nothing is deleted; uninstall is NOT a rollback path (parent cascade) —
  see docs/navigation_audit/navigation_rollback_plan.md.
- Standard apps that remain top-level by design: Calendar, Website,
  Link Tracker, Tests (developer).
""", 'author': 'Precisefect Solutions Pvt. Ltd.',
    'license': 'OPL-1',
    'depends': [
        'base', 'base_setup',
        # standard apps integrated into the workspace mapping
        'contacts', 'crm', 'website_slides', 'account', 'fleet', 'event',
        'spreadsheet_dashboard', 'mail', 'mass_mailing', 'im_livechat',
        # edicai modules owning reparented menus
        'edicai_academic', 'edicai_admission', 'edicai_ai', 'edicai_analytics',
        'edicai_api', 'edicai_appointment', 'edicai_asset_request',
        'edicai_assignment', 'edicai_attendance', 'edicai_base', 'edicai_calendar',
        'edicai_curriculum', 'edicai_digital_library', 'edicai_discipline',
        'edicai_documents', 'edicai_exam', 'edicai_faculty_profile', 'edicai_fees',
        'edicai_finance_report', 'edicai_grading', 'edicai_grievance', 'edicai_hostel',
        'edicai_library', 'edicai_lms', 'edicai_mentor', 'edicai_notice_board',
        'edicai_notify', 'edicai_placement', 'edicai_progression', 'edicai_quiz',
        'edicai_scholarship', 'edicai_secure_transcript', 'edicai_skill_assessment',
        'edicai_student', 'edicai_thesis', 'edicai_timetable', 'edicai_transport',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/menu_workspaces.xml',
        'wizards/navigation_preview_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edicai_navigation/static/src/js/preview_banner.js',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
