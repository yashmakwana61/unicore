# Navigation Risks & Findings

Computed from the live database dump (read-only). No records were modified.

## [hidden_inactive] Inactive (hidden) menu records still in DB

4 menu(s): mail.discuss_channel_integrations_menu Integrations; website.menu_website_dashboard eCommerce; website.menu_website_controller_pages_list Model Pages; sale.sale_menu_root Sales

## [duplicate_label] Duplicate menu label "General Settings" under same parent (parent base.menu_administration)

ids [7, 68] owned by ['base', 'base_setup']

## [duplicate_label] Duplicate menu label "Theme Store" under same parent (parent base.menu_apps)

ids [50, 52] owned by ['base']

## [shared_action] Multiple menus reuse action base_setup.action_general_configuration

menus [68, 190]: General Settings; Settings

## [shared_action] Multiple menus reuse action mail.mail_canned_response_action

menus [89, 329]: Canned Responses; Canned Responses

## [shared_action] Multiple menus reuse action mail.mail_blacklist_action

menus [106, 350]: Email Blacklist; Blacklisted Email Addresses

## [shared_action] Multiple menus reuse action calendar.action_calendar_event

menus [122, 123]: Calendar; Configuration

## [shared_action] Multiple menus reuse action calendar.action_calendar_alarm

menus [125, 128]: Reminders; Calendar Alarm

## [shared_action] Multiple menus reuse action link_tracker.link_tracker_action

menus [173, 349]: Link Tracker; Link Tracker

## [shared_action] Multiple menus reuse action account.res_partner_action_customer

menus [245, 412]: Customers; Customers

## [shared_action] Multiple menus reuse action product.product_category_action_form

menus [283, 433]: Product Categories; Categories

## [shared_action] Multiple menus reuse action sales_team.crm_team_action_config

menus [307, 427]: Sales Teams; Sales Teams

## [shared_action] Multiple menus reuse action sales_team.sales_team_crm_tag_action

menus [315, 429]: Tags; Tags

## [shared_action] Multiple menus reuse action website.website_visitors_action

menus [375, 399]: Visitors; Visitors

## [shared_action] Multiple menus reuse action payment.action_payment_provider

menus [383, 437, 517]: Payment Providers; Payment Providers; Payment Providers

## [shared_action] Multiple menus reuse action payment.action_payment_method

menus [384, 438, 518]: Payment Methods; Payment Methods; Payment Methods

## [shared_action] Multiple menus reuse action payment.action_payment_token

menus [385, 439, 519]: Payment Tokens; Payment Tokens; Payment Tokens

## [shared_action] Multiple menus reuse action payment.action_payment_transaction

menus [386, 440, 520]: Payment Transactions; Payment Transactions; Payment Transactions

## [shared_action] Multiple menus reuse action product.product_pricelist_action2

menus [419, 510]: Pricelists; Pricelists

## [shared_action] Multiple menus reuse action product.attribute_action

menus [431, 512]: Attributes; Attributes

## [shared_action] Multiple menus reuse action product.product_combo_action

menus [432, 513]: Combo Choices; Combo Choices

## [shared_action] Multiple menus reuse action product.product_tag_action

menus [434, 514]: Product Tags; Product Tags

## [shared_action] Multiple menus reuse action delivery.action_delivery_carrier_form

menus [444, 521]: Delivery Methods; Delivery Methods

## [shared_action] Multiple menus reuse action website_slides.slide_channel_action_overview

menus [450, 454, 708]: eLearning; Courses; Courses

## [shared_action] Multiple menus reuse action website_slides.slide_slide_action

menus [455, 709]: Contents; Contents (Slides)

## [shared_action] Multiple menus reuse action website_slides.slide_channel_action_report

menus [456, 711]: Courses; Course Analytics

## [shared_action] Multiple menus reuse action website_slides.rating_rating_action_slide_channel

menus [459, 712]: Reviews; Reviews

## [shared_action] Multiple menus reuse action website_slides.slide_channel_tag_group_action

menus [462, 714]: Course Groups; Course Tags

## [shared_action] Multiple menus reuse action edicai_asset_request.action_edicai_asset_request

menus [533, 534]: All Requests; New Request

## [shared_action] Multiple menus reuse action edicai_student_leave.action_student_leave_request

menus [720, 721]: All Leave Requests; Pending Approval

## [dead_grouping] Non-root menus with neither action nor children

12: base.menu_administration_shortcut Custom Shortcuts; base.menu_translation_app Application Terms; base.menu_config General Settings; base.theme_store Theme Store; mail.discuss_channel_integrations_menu Integrations; account.account_reports_partners_reports_menu Partner Reports; account.account_reports_taxes_and_fiscal_menu Taxes & Fiscal; account.account_reports_legal_statements_menu Statement Reports; account.account_report_folder Reporting; crm.menu_crm_config_opportunity Opportunities; crm.menu_import_crm Import & Synchronize; edicai_scholarship.menu_edicai_scholarship_config Configuration

## [action_no_xmlid] Menus whose action has no external XML ID

25: Third-Party Apps; Theme Store; Discuss; Discuss; Notifications; Voice & Video; Overview; Registration Desk; My Pipeline; Forecast; Configuration; Dashboards; Dashboards; Homepage; Menu Editor

## [cross_app_reuse] Menus owned by modules mounted under another app root

edicai_base: 44 menu(s); edicai_grading: 6 menu(s)

## [menus_without_xmlid] Menu records without any external ID

0 menu(s): 

## [orphan_parent] Menus whose parent record is missing

0 menu(s): 

## Security-relevant observations

- Menu group restrictions (visible above) are visibility only; ACL/record-rule separation must be preserved (they were inventoried, not altered).
- `edicai_api.group_edicai_api_user` currently *implies* `edicai_api.group_edicai_api_admin` — verify intent; normally the admin group implies the user group.
- `edicai_base.group_edicai_admin` is not implied by any tracked custom group; implied chain: Faculty/Staff/Registrar/Finance/Manager → Admin. Initial grants may rely on manual assignment.

### Duplicate labels table (name → menus)

| Name | Menu IDs | Owners |
|---|---|---|
| General Settings | 7, 68 | base, base_setup |
| Theme Store | 50, 52 | base, base |