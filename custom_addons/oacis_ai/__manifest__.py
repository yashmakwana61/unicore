{
    'name': 'Oacis AI',
    'version': '19.0.1.0.0',
    'category': 'Oacis/AI',
    'summary': 'AI-Powered Assistant for Oacis — Powered by OpenCode Zen',
    'description': """
Oacis AI — Intelligent Assistant Module
==========================================

Integrates OpenCode Zen (OpenAI-compatible) AI capabilities across the
Oacis Education Management Suite:

* **AI Text Generation Wizard** — Generate, rewrite, summarise, and
  enhance text content from anywhere in the system.
* **Interactive AI Chatbot** — A persistent chat panel accessible via
  the systray for natural-language interaction with the AI.
* **Configurable Provider** — API key, model, and temperature settings
  managed through Odoo General Settings.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'base',
        'base_setup',
        'mail',
        'oacis_base',
    ],
    'data': [
        # Security
        'security/oacis_ai_groups.xml',
        'security/ir.model.access.csv',
        # Views & Wizards (actions must be defined before menus)
        'views/res_config_settings_views.xml',
        'views/oacis_ai_chat_views.xml',
        'wizard/ai_generate_wizard_views.xml',
        # Menus
        'views/oacis_ai_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'oacis_ai/static/src/css/oacis_ai_chatbot.css',
            'oacis_ai/static/src/js/oacis_ai_chatbot.js',
            'oacis_ai/static/src/xml/oacis_ai_chatbot.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'web_icon': 'oacis_ai,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
