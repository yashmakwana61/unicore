# -*- coding: utf-8 -*-
import json

from odoo import http
from odoo.http import request


class NavigationPreviewController(http.Controller):
    """State endpoint used by the frontend preview badge."""

    @http.route('/edicai_navigation/preview_state', type='http', auth='user',
                methods=['GET'], sitemap=False)
    def preview_state(self):
        state = request.env['navigation.preview.util'].sudo()._state()
        return request.make_json_response({'state': state},
                                          headers={'Cache-Control': 'no-store'})
