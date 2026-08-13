import json

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    theme_font_family = fields.Selection([
        ('', 'Company Default'),
        ('system', 'System Default'),
        ('inter', 'Inter'),
        ('roboto', 'Roboto'),
        ('outfit', 'Outfit'),
    ], string='Theme Font Family')

    theme_list_density = fields.Selection([
        ('', 'Company Default'),
        ('default', 'Default'),
        ('comfortable', 'Comfortable'),
        ('compact', 'Compact'),
    ], string='Theme List Density')

    theme_border_radius = fields.Selection([
        ('', 'Company Default'),
        ('none', 'None'),
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
    ], string='Theme Border Radius')

    theme_chatter_position = fields.Selection([
        ('', 'Company Default'),
        ('bottom', 'Bottom'),
        ('side', 'Side'),
    ], string='Theme Chatter Position')

    theme_pinned_apps = fields.Many2many(
        'ir.ui.menu',
        string='Pinned Start Menu Apps',
        help="Apps pinned to the Favourites list of the Start Menu.",
    )

    theme_workspace_items = fields.Text(
        string='Workspace Items',
        help="JSON-encoded workspace entries for the Start Menu.",
        default='[]',
    )

    theme_recent_menus = fields.Text(
        string='Recent Menu History',
        help="JSON-encoded list of recently accessed menu IDs.",
        default='[]',
    )

    def theme_toggle_pinned_app(self, menu_id):
        self.ensure_one()
        menu = self.env['ir.ui.menu'].browse(int(menu_id))
        if menu in self.theme_pinned_apps:
            self.theme_pinned_apps -= menu
        else:
            self.theme_pinned_apps |= menu
        return self.theme_pinned_apps.ids

    def theme_set_home_action(self, action_id):
        """Set the user's home action (the action loaded on login)."""
        self.ensure_one()
        self.action_id = int(action_id) if action_id else False
        return True

    def theme_add_recent_menu(self, menu_id):
        """Track a menu visit in the user's recent history (max 20 items)."""
        self.ensure_one()
        try:
            recents = json.loads(self.theme_recent_menus or '[]')
        except (json.JSONDecodeError, TypeError):
            recents = []
        menu_id = int(menu_id)
        # Remove duplicates, then prepend
        recents = [m for m in recents if m != menu_id]
        recents.insert(0, menu_id)
        recents = recents[:20]
        self.theme_recent_menus = json.dumps(recents)
        return recents

    def theme_get_workspace_data(self):
        """Return structured workspace data for the Start Menu."""
        self.ensure_one()
        # Parse workspace items
        try:
            workspace_items = json.loads(self.theme_workspace_items or '[]')
        except (json.JSONDecodeError, TypeError):
            workspace_items = []

        # Parse recent menus and enrich with menu info
        try:
            recent_ids = json.loads(self.theme_recent_menus or '[]')
        except (json.JSONDecodeError, TypeError):
            recent_ids = []

        recents = []
        for mid in recent_ids[:10]:
            menu = self.env['ir.ui.menu'].browse(mid)
            if menu.exists():
                # Find the root app for this menu
                parent = menu
                while parent.parent_id:
                    parent = parent.parent_id
                recents.append({
                    'id': menu.id,
                    'name': menu.name,
                    'app_name': parent.name,
                    'action_id': menu.action.id if menu.action else False,
                    'full_name': f"{parent.name}: {menu.name}" if parent.id != menu.id else menu.name,
                })
        return {
            'workspace_items': workspace_items,
            'recents': recents,
        }

    def theme_save_workspace_items(self, items):
        """Persist workspace items (list of dicts with category, name, menu_id)."""
        self.ensure_one()
        self.theme_workspace_items = json.dumps(items)
        return True

    def theme_delete_workspace_item(self, item_index):
        """Delete a workspace item by index."""
        self.ensure_one()
        try:
            items = json.loads(self.theme_workspace_items or '[]')
        except (json.JSONDecodeError, TypeError):
            items = []
        if 0 <= item_index < len(items):
            items.pop(item_index)
        self.theme_workspace_items = json.dumps(items)
        return items

    def _get_oacis_theme_config(self):
        self.ensure_one()
        company = self.company_id
        return {
            'theme_font_family': self.theme_font_family or company.theme_font_family or 'system',
            'theme_list_density': self.theme_list_density or company.theme_list_density or 'default',
            'theme_border_radius': self.theme_border_radius or company.theme_border_radius or 'medium',
            'theme_chatter_position': self.theme_chatter_position or company.theme_chatter_position or 'bottom',
            'theme_start_menu_bg': company.theme_start_menu_bg or 'aurora',
        }
