# docs/studio_plan.md §15 — Studio Home metrics API
from odoo import http
from odoo.http import request

class StudioHomeController(http.Controller):

    @http.route('/studio/metrics', type='json', auth='user')
    def studio_metrics(self):
        # Enforce Studio User group
        if not request.env.user.has_group('oacis_studio.group_studio_user'):
            return {'error': 'Studio User access required'}
        env = request.env
        data = {
            'apps_total': env['studio.app'].search_count([]),
            'apps_published': env['studio.app'].search_count([('state','=','published')]),
            'apps_draft': env['studio.app'].search_count([('state','=','draft')]),
            'models_total': env['studio.model'].search_count([]),
            'fields_total': env['studio.field'].search_count([]),
            'dictionary_models': env['studio.data.dictionary'].search_count([('ttype','=','model')]),
            'dictionary_total': env['studio.data.dictionary'].search_count([]),
            'records_total': env['studio.record'].search_count([]),
            'ai_requests': env['studio.ai.request'].search_count([]),
            'recent_apps': [
                {'id': r.id, 'name': r.name, 'key': r.key, 'state': r.state, 'version': r.version}
                for r in env['studio.app'].search([], order='write_date desc', limit=5)
            ],
            'recent_versions': [
                {'app': v.app_id.name, 'name': v.name, 'hash': v.dsl_hash, 'date': str(v.create_date)}
                for v in env['studio.version'].search([], order='create_date desc', limit=5)
            ],
        }
        return data

    @http.route('/studio/export/<int:app_id>', type='http', auth='user')
    def studio_export(self, app_id, **kw):
        if not request.env.user.has_group('oacis_studio.group_studio_user'):
            return request.not_found()
        app = request.env['studio.app'].browse(app_id).sudo()
        if not app.exists():
            return request.not_found()
        import json
        payload = json.dumps(app.dsl_json or {}, indent=2, ensure_ascii=False)
        headers = [
            ('Content-Type', 'application/json'),
            ('Content-Disposition', f'attachment; filename={app.key}.studio.json'),
        ]
        return request.make_response(payload, headers)
