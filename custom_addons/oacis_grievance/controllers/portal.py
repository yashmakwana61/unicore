from odoo import http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal


class GrievancePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'grievance_count' in counters:
            values['grievance_count'] = request.env['oacis.grievance.request'].search_count([
                ('raised_by_id', '=', request.env.user.partner_id.id),
            ])
        return values

    @http.route(['/my/grievances', '/my/grievances/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_grievances(self, **kwargs):
        values = self._prepare_portal_layout_values()
        Grievance = request.env['oacis.grievance.request']
        domain = [('raised_by_id', '=', request.env.user.partner_id.id)]
        grievances = Grievance.search(domain)
        values.update({
            'grievances': grievances,
            'page_name': 'grievance',
            'default_url': '/my/grievances',
        })
        return request.render("oacis_grievance.portal_my_grievances", values)

    @http.route(['/my/grievance/new'], type='http', auth="user", website=True)
    def portal_my_grievance_new(self, **kwargs):
        categories = request.env['oacis.grievance.category'].search([])
        values = {
            'categories': categories,
            'page_name': 'grievance_new',
        }
        return request.render("oacis_grievance.portal_grievance_new", values)

    @http.route(['/my/grievance/submit'], type='http', auth="user", website=True, methods=['POST'])
    def portal_my_grievance_submit(self, **post):
        category_id = int(post.get('category_id'))
        description = post.get('description')
        request.env['oacis.grievance.request'].sudo().create({
            'category_id': category_id,
            'description': description,
            'raised_by_id': request.env.user.partner_id.id,
        })
        return request.redirect('/my/grievances')
