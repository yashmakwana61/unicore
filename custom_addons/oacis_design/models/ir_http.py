from odoo import api, models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super().session_info()
        user = self.env.user
        if user:
            res['unicore_theme_config'] = user._get_unicore_theme_config()
            res['unicore_theme_pinned_apps'] = user.theme_pinned_apps.ids
            res['unicore_workspace_data'] = user.theme_get_workspace_data()
        return res

    @api.model
    def lazy_session_info(self):
        res = super().lazy_session_info()
        user = self.env.user
        if user and user._is_internal():
            config = user._get_unicore_theme_config()
            # Generate a simple hash based on the current configuration values
            theme_hash = f"{config['theme_font_family']}-{config['theme_list_density']}-{config['theme_border_radius']}-{config['theme_chatter_position']}-{config['theme_start_menu_bg']}"
            res['unicore_theme_hash'] = theme_hash
        return res
