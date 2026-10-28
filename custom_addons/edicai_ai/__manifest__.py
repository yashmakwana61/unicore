{
    'name': 'Edicai AI',
    'version': '19.0.2.0.0',
    'category': 'Edicai/AI',
    'summary': 'AI-Powered Assistant for Edicai — Powered by OpenCode Zen',
    'description': """
Edicai AI — Intelligent Assistant Module
==========================================

Integrates OpenCode Zen (OpenAI-compatible) AI capabilities across the
Edicai Education Management Suite:

* **Interactive AI Chatbot** — Systray slide-out panel with history search,
  prompt templates, copy buttons, feedback, and "summarize this record".
* **Portal AI Assistant** — `/my/ai-assistant` page for students/guardians
  reusing the same private, permission-checked APIs.
* **AI Text Generation Wizard** — Generate, rewrite, summarise, translate,
  create quizzes, draft notices; optionally insert the result back into
  the originating record field.
* **Prompt Library** — Reusable one-click starters per category
  (admission / academic / fees / general).
* **Record-aware answers** — Optional grounding in whitelisted Odoo records
  (student, admission, enrollment, assignment, exam) with strict ACL checks.
* **Governance** — Usage logs with token estimates, per-user rate limits,
  Test Connection button, and configurable assistant personality.
* **Configurable Provider** — API key, model, system prompt, temperature,
  max tokens managed through Odoo General Settings.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'base',
        'base_setup',
        'mail',
        'portal',
        'edicai_base',
    ],
    'data': [
        # Security
        'security/edicai_ai_groups.xml',
        'security/ir.model.access.csv',
        'security/edicai_ai_record_rules.xml',
        # Data (prompt seeds)
        'data/edicai_ai_prompt_data.xml',
        # Views & Wizards (actions must be defined before menus)
        'views/res_config_settings_views.xml',
        'views/edicai_ai_chat_views.xml',
        'views/edicai_ai_library_views.xml',
        'wizard/ai_generate_wizard_views.xml',
        'views/portal_templates.xml',
        # Menus
        'views/edicai_ai_menus.xml',
        # Audit trail + Workspace (menuitems hang off menu_edicai_ai_root)
        'views/edicai_ai_audit_views.xml',
        'views/edicai_ai_workspace_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edicai_ai/static/src/css/edicai_ai_chatbot.css',
            'edicai_ai/static/src/css/edicai_ai_workspace.css',
            'edicai_ai/static/src/js/edicai_ai_chatbot.js',
            'edicai_ai/static/src/xml/edicai_ai_chatbot.xml',
            'edicai_ai/static/src/js/edicai_ai_workspace.js',
            'edicai_ai/static/src/xml/edicai_ai_workspace.xml',
        ],
        'web.assets_frontend': [
            'edicai_ai/static/src/js/edicai_ai_portal.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'web_icon': 'edicai_ai,static/description/icon.png',
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
