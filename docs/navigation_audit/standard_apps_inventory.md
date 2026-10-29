# Standard Odoo Apps — Live Inventory (DB edicai_preview clone / dump of edicai)

From `ir.ui.menu` dump (695 rows total). Standard roots = every root owned
by a non-custom module. "App" = root menu with children in the launcher.

| App / root | XML ID | DB id | Active | Direct children | All descendants | Action on first actionable leaf | Menu groups |
|---|---|---|---|---|---|---|---|
| Apps | `base.menu_management` | 15 | active | 4 | 8 | Update Apps List (ir.actions.act_window) | — |
| Calendar | `calendar.mail_menu_calendar` | 121 | active | 2 | 4 | Calendar (ir.actions.act_window) | base.group_user |
| Contacts | `contacts.menu_contacts` | 129 | active | 2 | 11 | Contacts (ir.actions.act_window) | base.group_user ; base.group_partner_manager |
| CRM | `crm.crm_menu_root` | 292 | active | 5 | 28 | Leads (ir.actions.act_window) | sales_team.group_sale_salesman ; sales_team.group_sale_manager |
| Dashboards | `spreadsheet_dashboard.spreadsheet_dashboard_menu_root` | 355 | active | 2 | 3 | Dashboards (ir.actions.client) | — |
| Discuss | `mail.menu_root_discuss` | 83 | active | 5 | 10 | Discuss (ir.actions.client) | base.group_user |
| eLearning | `website_slides.website_slides_menu_root` | 450 | active | 3 | 14 | Settings (ir.actions.act_window) | website_slides.group_website_slides_officer |
| Email Marketing | `mass_mailing.mass_mailing_menu_root` | 336 | active | 5 | 16 | Mailings (ir.actions.act_window) | mass_mailing.group_mass_mailing_user |
| Events | `event.event_main_menu` | 226 | active | 4 | 12 | Events (ir.actions.act_window) | event.group_event_registration_desk |
| Fleet | `fleet.menu_root` | 145 | active | 3 | 20 | Costs (ir.actions.act_window) | fleet.fleet_group_user |
| Invoicing | `account.menu_finance` | 238 | active | 7 | 56 | Dashboard (ir.actions.act_window) | account.group_account_readonly ; account.group_account_invoice |
| Link Tracker | `utm.menu_link_tracker_root` | 75 | active | 2 | 5 | Link Tracker (ir.actions.act_window) | base.group_no_one |
| Live Chat | `im_livechat.menu_livechat_root` | 321 | active | 6 | 20 | Channels (ir.actions.act_window) | im_livechat.im_livechat_group_user |
| Sales | `sale.sale_menu_root` | 407 | INACTIVE (hidden) | 5 | 39 | Settings (ir.actions.act_window) | — |
| Settings | `base.menu_administration` | 1 | active | 7 | 116 | General Settings (ir.actions.act_window) | base.group_erp_manager ; base.group_system |
| Tests | `base.menu_tests` | 16 | active | 0 | 0 | — | — |
| Website | `website.menu_website_configuration` | 359 | active | 4 | 50 | Products (ir.actions.act_window) | base.group_user |

**Totals:** 17 standard roots; 429 standard menus (roots + descendants).
## Installed / Unavailable / Unverified status (per ir_module_module)

| App root | Owner module | Status | Notes for the combined nav |
|---|---|---|---|
| Contacts | `contacts` | **installed** (v19.0.1.0) | verified in live DB — eligible for the combined mapping |
| CRM | `crm` | **installed** (v19.0.1.9) | verified in live DB — eligible for the combined mapping |
| eLearning | `website_slides` | **installed** (v19.0.2.7) | verified in live DB — eligible for the combined mapping |
| Invoicing | `account` | **installed** (v19.0.1.5) | verified in live DB — eligible for the combined mapping |
| Fleet | `fleet` | **installed** (v19.0.0.1) | verified in live DB — eligible for the combined mapping |
| Events | `event` | **installed** (v19.0.1.9) | verified in live DB — eligible for the combined mapping |
| Dashboards | `spreadsheet_dashboard` | **installed** (v19.0.1.0) | verified in live DB — eligible for the combined mapping |
| Discuss | `mail` | **installed** (v19.0.1.19) | verified in live DB — eligible for the combined mapping |
| Email Marketing | `mass_mailing` | **installed** (v19.0.2.7) | verified in live DB — eligible for the combined mapping |
| Live Chat | `im_livechat` | **installed** (v19.0.1.0) | verified in live DB — eligible for the combined mapping |
| Apps | `base` | **installed** (v19.0.1.3) | verified in live DB — eligible for the combined mapping |
| Settings | `base` | **installed** (v19.0.1.3) | verified in live DB — eligible for the combined mapping |
| Calendar | `calendar` | **installed** (v19.0.1.1) | verified in live DB — eligible for the combined mapping |
| Website | `website` | **installed** (v19.0.1.0) | verified in live DB — eligible for the combined mapping |
| Link Tracker | `utm` | **installed** (v19.0.1.1) | verified in live DB — eligible for the combined mapping |
| Sales | `sale` | **installed** (v19.0.1.2) | verified in live DB — eligible for the combined mapping |
| Tests | `base` | **installed** (v19.0.1.3) | verified in live DB — eligible for the combined mapping |

Application confirmed NOT separately installed (menu absent or root hidden): Point of Sale, Studio, Helpdesk etc. (no `ir.ui.menu` root found).

Special notes:
- `sale.sale_menu_root` exists but is **inactive** in the dump — do not touch.
- `base.menu_tests` is a developer-only root — leave unchanged.
- `calendar` + `website` remain top-level apps in the combined design (Website: accessible to editors; Calendar: cross-functional scheduling entry).