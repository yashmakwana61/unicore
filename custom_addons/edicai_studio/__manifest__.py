{
    'name': 'Forge Studio — AI No-Code Platform (Odoo Studio UX Parity)',
    'version': '19.0.2.0.0',
    'category': 'Education',
    'summary': 'Odoo Studio UX Parity: 3-pane shell, Selection Manager, Properties, Drag-Drop, AI Copilot',
    'description': """
Forge Studio Phase 8 — Security & Versioning (Hardening)
==============================================
Implements the core platform layer described in docs/studio_plan.md:

* Studio DSL 1.0 (JSON Schema) — validated, versioned, previewable
* Metadata models: studio.app/model/field/view/dataset/security/version/dictionary/ai_request
* Hybrid runtime: JSONB studio.record for instant apps (no registry reload), opt-in x_ materialization
* Data Dictionary crawler over 50+ edicai_* modules
* Validation engine (deterministic, no LLM) + permission & preview gates
* Foundation for Model Builder, View Builder, Workflow, Automation, Report & Dashboard Studio

All mutating AI tools emit DSL only; runtime is the sole DB writer.
See docs/studio_plan.md §2-§4, §9, §11, §17.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'base',
        'mail',
        'web',
        'edicai_base',
        'edicai_security',
    ],
    'data': [
        'security/edicai_studio_groups.xml',
        'security/ir.model.access.csv',
        'security/edicai_studio_security.xml',
        'data/studio_sequence.xml',
        'views/studio_app_views.xml',
        'views/studio_model_views.xml',
        'views/studio_field_views.xml',
        'views/studio_view_views.xml',
        'views/studio_dataset_views.xml',
        'views/studio_security_views.xml',
        'views/studio_version_views.xml',
        'views/studio_data_dictionary_views.xml',
        'views/studio_ai_request_views.xml',
        'views/studio_ai_views.xml',
        'views/studio_record_views.xml',
        'views/studio_home_views.xml',
        'views/studio_workflow_views.xml',
        'views/studio_automation_views.xml',
        'views/studio_report_views.xml',
        'views/studio_dashboard_views.xml',
        'views/studio_shell_views.xml',
        'views/studio_command_palette_views.xml',
        'wizards/studio_import_wizard_views.xml',
        'wizards/studio_export_wizard_views.xml',
        'menus/edicai_studio_menus.xml',
        'data/studio_cron.xml',
        'data/studio_report_templates.xml',
        'data/studio_dashboard_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edicai_studio/static/src/js/studio_builder.js',
            'edicai_studio/static/src/js/studio_home.js',
            'edicai_studio/static/src/js/studio_model_builder.js',
            'edicai_studio/static/src/js/studio_view_builder.js',
            'edicai_studio/static/src/js/studio_workflow_builder.js',
            'edicai_studio/static/src/js/studio_automation_builder.js',
            'edicai_studio/static/src/js/studio_report_builder.js',
            'edicai_studio/static/src/js/studio_dashboard_builder.js',
            'edicai_studio/static/src/js/studio_ai_copilot.js',
            'edicai_studio/static/src/js/studio_shell.js',
            'edicai_studio/static/src/js/studio_contextual.js',
            'edicai_studio/static/src/js/studio_command_palette.js',
            'edicai_studio/static/src/xml/studio_builder.xml',
            'edicai_studio/static/src/xml/studio_home.xml',
            'edicai_studio/static/src/xml/studio_model_builder.xml',
            'edicai_studio/static/src/xml/studio_view_builder.xml',
            'edicai_studio/static/src/xml/studio_workflow_builder.xml',
            'edicai_studio/static/src/xml/studio_automation_builder.xml',
            'edicai_studio/static/src/xml/studio_report_builder.xml',
            'edicai_studio/static/src/xml/studio_dashboard_builder.xml',
            'edicai_studio/static/src/xml/studio_ai_copilot.xml',
            'edicai_studio/static/src/xml/studio_shell.xml',
            'edicai_studio/static/src/xml/studio_contextual.xml',
            'edicai_studio/static/src/xml/studio_command_palette.xml',
            'edicai_studio/static/src/scss/studio_builder.scss',
            'edicai_studio/static/src/scss/studio_shell.scss',
        ],
    },
    'images': ['static/description/icon.png'],
    'web_icon': 'edicai_studio,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
