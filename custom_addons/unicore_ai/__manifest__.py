# -*- coding: utf-8 -*-
{
    'name': 'Unicore AI',
    'version': '19.0.1.0.0',
    'category': 'Unicore/AI',
    'summary': 'AI-Powered Assistant for Unicore — Powered by OpenCode Zen',
    'description': """
Unicore AI — Intelligent Assistant Module
==========================================

Integrates OpenCode Zen (OpenAI-compatible) AI capabilities across the
Unicore Education Management Suite:

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
        'unicore_base',
    ],
    'data': [
        # Security
        'security/unicore_ai_groups.xml',
        'security/ir.model.access.csv',
        # Views & Wizards (actions must be defined before menus)
        'views/res_config_settings_views.xml',
        'views/unicore_ai_chat_views.xml',
        'wizard/ai_generate_wizard_views.xml',
        # Menus
        'views/unicore_ai_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'unicore_ai/static/src/css/unicore_ai_chatbot.css',
            'unicore_ai/static/src/js/unicore_ai_chatbot.js',
            'unicore_ai/static/src/xml/unicore_ai_chatbot.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_ai,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
