from odoo import http
from odoo.http import request

# Side-by-side chatter layout for Odoo 19.
#
# The JS service adds the `o_unicore_chatter_side` class on the `.o_form_view`
# root, so no `:has()` is needed. In 19.x the side-by-side split happens inside
# `.o_form_renderer` (its flex children are `.o_form_sheet_bg` and
# `.o-mail-Form-chatter`).
#
# Odoo 19 wraps the form in a fixed-height, overflow:hidden action area
# (`.o_action_manager > .o_action { height: 100%; overflow: hidden; }`), so the
# form itself must fill that area (`height: 100%`) and scroll INTERNALLY. Making
# the form auto-height just lets it overflow the clipped action area, which is
# what caused "cannot scroll down in records". We therefore restore the stock
# `height: 100%` model and split the renderer into two independently scrolling
# panes: the sheet (left) and the chatter (right).
SIDE_CHATTER_CSS = """
@media (min-width: 992px) {
    .o_form_view.o_unicore_chatter_side {
        flex-flow: column nowrap !important;
        height: 100% !important;
        min-height: 0 !important;
        overflow: hidden !important;
    }

    .o_form_view.o_unicore_chatter_side > .o_form_view_container {
        flex: 1 1 auto !important;
        height: 100% !important;
        width: auto !important;
        max-width: 100% !important;
        min-width: 0 !important;
    }

    .o_form_view.o_unicore_chatter_side .o_form_view_container .o_content {
        overflow: hidden !important;
    }

    .o_form_view.o_unicore_chatter_side .o_form_renderer {
        display: flex !important;
        flex-flow: row nowrap !important;
        height: 100% !important;
        overflow: hidden !important;
    }

    .o_form_view.o_unicore_chatter_side .o_form_renderer .o_form_sheet_bg {
        flex: 2 1 0% !important;
        min-width: 0 !important;
        max-width: none !important;
        overflow: auto !important;
    }

    .o_form_view.o_unicore_chatter_side .o_form_renderer .o-mail-Form-chatter.o-aside:not(.o-isInFormSheetBg) {
        flex: 0 0 33.333333% !important;
        width: 33.333333% !important;
        max-width: 33.333333% !important;
        min-width: 33.333333% !important;
        height: auto !important;
        min-height: 0 !important;
        overflow: auto !important;
        border-left: 1px solid #e0e0e0 !important;
        border-top: none !important;
    }
}

@media (max-width: 991.98px) {
    .o_form_view.o_unicore_chatter_side .o_form_renderer {
        flex-flow: column nowrap !important;
        overflow: auto !important;
    }

    .o_form_view.o_unicore_chatter_side .o_form_renderer .o_form_sheet_bg {
        flex: 0 0 auto !important;
        max-width: 100% !important;
        overflow: visible !important;
    }

    .o_form_view.o_unicore_chatter_side .o_form_renderer .o-mail-Form-chatter.o-aside {
        flex: 0 0 auto !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        overflow: visible !important;
        border-left: none !important;
    }
}
"""

# Stacked (bottom) chatter layout. The renderer stays a column and becomes the
# single internal scroller for the whole sheet + chatter stack, overriding the
# native XXL row layout.
BOTTOM_CHATTER_CSS = """
@media (min-width: 992px) {
    .o_form_view.o_unicore_chatter_bottom {
        flex-flow: column nowrap !important;
        height: 100% !important;
        min-height: 0 !important;
        overflow: hidden !important;
    }

    .o_form_view.o_unicore_chatter_bottom > .o_form_view_container {
        flex: 1 1 auto !important;
        height: 100% !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
    }

    .o_form_view.o_unicore_chatter_bottom .o_form_view_container .o_content {
        overflow: hidden !important;
    }

    .o_form_view.o_unicore_chatter_bottom .o_form_renderer {
        display: flex !important;
        flex-flow: column nowrap !important;
        height: 100% !important;
        overflow: auto !important;
    }

    .o_form_view.o_unicore_chatter_bottom .o_form_renderer .o_form_sheet_bg {
        flex: 0 0 auto !important;
        overflow: visible !important;
        min-height: 0 !important;
    }

    .o_form_view.o_unicore_chatter_bottom .o_form_renderer .o-mail-Form-chatter:not(.o-aside):not(.o-isInFormSheetBg) {
        flex: 0 0 auto !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        border-left: none !important;
        border-top: 1px solid #e0e0e0 !important;
    }
}
"""


class UnicoreDesignController(http.Controller):

    @http.route('/unicore_design/theme.css', type='http', auth='user', readonly=True)
    def theme_css(self, **kwargs):
        user = request.env.user
        config = user._get_unicore_theme_config()

        # Map Font Family
        font_map = {
            'system': 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
            'inter': '"Inter", sans-serif',
            'roboto': '"Roboto", sans-serif',
            'outfit': '"Outfit", sans-serif',
        }
        font_family = font_map.get(config.get('theme_font_family'), font_map['system'])

        # Map Border Radius
        radius_map = {
            'none': '0px',
            'small': '4px',
            'medium': '8px',
            'large': '16px',
        }
        border_radius = radius_map.get(config.get('theme_border_radius'), radius_map['medium'])

        # Map Start Menu Background
        startmenu_bg_map = {
            'none': 'rgba(28, 32, 46, 0.96)',
            'aurora': 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
            'ocean': 'linear-gradient(135deg, #0f2027 0%, #203a43 45%, #2c5364 100%)',
            'sunset': 'linear-gradient(135deg, #f83600 0%, #dd6e4b 45%, #f9d423 100%)',
            'midnight': 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)',
        }
        startmenu_bg = startmenu_bg_map.get(
            config.get('theme_start_menu_bg'), startmenu_bg_map['aurora'],
        )

        # Map List Density Padding
        density_css = ""
        density = config.get('theme_list_density', 'default')
        if density == 'comfortable':
            density_css = """
.o_list_renderer .o_data_row > td,
.o_list_renderer .o_data_row > th {
    padding-top: 12px !important;
    padding-bottom: 12px !important;
}"""
        elif density == 'compact':
            density_css = """
.o_list_renderer .o_data_row > td,
.o_list_renderer .o_data_row > th {
    padding-top: 4px !important;
    padding-bottom: 4px !important;
}"""

        # Map Chatter Position Layout (Always serve both layouts so switching position in OWL is instant)
        chatter_css = SIDE_CHATTER_CSS + "\n" + BOTTOM_CHATTER_CSS

        # Build dynamic CSS
        css_content = f""":root {{
    --unicore-font-family: {font_family};
    --unicore-border-radius: {border_radius};
    --unicore-startmenu-bg: {startmenu_bg};
    --unicore-startmenu-blur: 16px;
}}

body, .o_web_client, input, button, select, textarea, .btn, .o_input {{
    font-family: var(--unicore-font-family) !important;
}}

.btn, .form-control, .form-select, .o_input, .dropdown-menu, .modal-content, .card, .o_field_widget, .o_statusbar_buttons > button {{
    border-radius: var(--unicore-border-radius) !important;
}}
{density_css}
{chatter_css}
"""
        return request.make_response(
            css_content,
            headers=[
                ('Content-Type', 'text/css'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ],
        )
