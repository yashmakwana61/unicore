# docs/studio_plan.md §11 — AI Copilot HTTP (Phase 7)
from odoo import http
from odoo.http import request
import json

class StudioAIController(http.Controller):

    @http.route('/studio/ai/chat', type='json', auth='user')
    def ai_chat(self, prompt, app_id=None):
        # Enforce Studio User
        if not request.env.user.has_group('oacis_studio.group_studio_user'):
            return {'error': 'Studio User access required'}
        copilot = request.env['studio.ai.copilot']
        result = copilot.chat(prompt, app_id=app_id)
        return result

    @http.route('/studio/ai/publish', type='json', auth='user')
    def ai_publish(self, request_id, app_id=None):
        if not request.env.user.has_group('oacis_studio.group_studio_builder'):
            return {'error': 'Studio Builder access required to publish'}
        copilot = request.env['studio.ai.copilot']
        result = copilot.publish(request_id, app_id=app_id)
        return result

    @http.route('/studio/ai/tools', type='json', auth='user')
    def ai_tools(self):
        if not request.env.user.has_group('oacis_studio.group_studio_user'):
            return {'error': 'Studio User access required'}
        # Return tool specs for frontend
        from odoo.addons.oacis_studio.models.studio_ai_copilot import TOOL_SPECS
        return TOOL_SPECS
