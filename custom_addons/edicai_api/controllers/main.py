from datetime import datetime

from odoo import http
from odoo.http import request

from odoo.addons.edicai_api.controllers.common import (
    _require_scope,
    _safe_call,
    api_error,
    api_response,
    validate_api_key,
)


class EdicaiApiMain(http.Controller):

    @http.route('/api/edicai/v1/health', type='http', auth='public',
                methods=['GET'], csrf=False)
    def health(self, **kwargs):
        return api_response({
            'status': 'UP',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '19.0.1.0.0',
            'service': 'Edicai API',
        })

    @http.route('/api/edicai/v1/info', type='http', auth='public',
                methods=['GET'], csrf=False)
    def info(self, **kwargs):
        return _safe_call(self._info, **kwargs)

    def _info(self, **kwargs):
        api_key = validate_api_key(request)
        if not api_key:
            return api_error('Invalid or missing API key.',
                             'UNAUTHORIZED', 401)
        if not _require_scope(api_key, 'read'):
            return api_error('API key scope does not allow info access.',
                             'FORBIDDEN', 403)
        user = api_key.user_id
        IrModule = request.env['ir.module.module']
        modules = IrModule.sudo().search([
            ('name', 'like', 'edicai_'),
            ('state', '=', 'installed'),
        ])
        return api_response({
            'institution': user.company_id.name,
            'user': user.name,
            'scope': api_key.scope,
            'modules': [m.name for m in modules],
            'timestamp': datetime.utcnow().isoformat(),
        })
