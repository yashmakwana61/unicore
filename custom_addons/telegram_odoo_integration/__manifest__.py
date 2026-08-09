{
    'name': 'Telegram Odoo Integration',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Create Sales Orders automatically from Telegram bot messages',
    'description': """
Telegram Odoo Integration
=========================

Connect a Telegram bot to Odoo through a webhook and create Sales Orders
automatically from chat messages.

Features
--------
* Public JSON webhook endpoint ``/telegram/webhook`` for Telegram updates.
* Configurable bot token and allowed chat id (Settings > Telegram).
* Automatic customer (``res.partner``) lookup/creation from the Telegram
  username and chat id.
* Order message parser: ``Order: Product Qty:2 Price:100`` (case-insensitive
  keywords). Multiple products per message are supported with comma or
  newline separated items.
* Automatic product lookup/creation with list price.
* Sales Order + Sales Order Lines creation (draft state).
* Reply to the user through the Telegram Bot API (``sendMessage``).
* Full Telegram chat history stored in ``telegram.message`` with a dedicated
  "Telegram Orders" menu under Sales > Orders and a stat button on the
  Sales Order form.
* Audit logging of every update and JSON error responses.

Compatibility: Odoo 19 Community Edition (also runs on Odoo 16 / 17 with a
version prefix change in this manifest).
""",
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/telegram_message_views.xml',
        'views/sale_order_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
