import logging

from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager

_logger = logging.getLogger(__name__)


class GrievancePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'grievance_count' in counters:
            values['grievance_count'] = request.env['oacis.grievance.request'].search_count([
                ('raised_by_id', '=', request.env.user.partner_id.id),
            ])
        return values

    @http.route(['/my/grievances', '/my/grievances/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_grievances(self, page=1, sortby=None, **kwargs):
        values = self._prepare_portal_layout_values()
        Grievance = request.env['oacis.grievance.request']
        domain = [('raised_by_id', '=', request.env.user.partner_id.id)]

        url = '/my/grievances'
        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc, id desc'},
            'date_asc': {'label': _('Oldest'), 'order': 'create_date asc, id asc'},
            'state': {'label': _('Status'), 'order': 'state asc, create_date desc'},
        }
        if not sortby or sortby not in searchbar_sortings:
            sortby = 'date'
        grievance_count = Grievance.search_count(domain)
        pager_vals = portal_pager(
            url=url,
            total=grievance_count,
            page=page,
            step=10,
            scope=5,
            url_args={'sortby': sortby},
        )
        grievances = Grievance.search(
            domain,
            order=searchbar_sortings[sortby]['order'],
            limit=pager_vals['step'],
            offset=pager_vals['offset'],
        )
        values.update({
            'grievances': grievances,
            'page_name': 'grievance',
            'default_url': url,
            'pager': pager_vals,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render("oacis_grievance.portal_my_grievances", values)

    @http.route(['/my/grievance/new'], type='http', auth="user", website=True)
    def portal_my_grievance_new(self, **kwargs):
        categories = request.env['oacis.grievance.category'].search([])
        values = {
            'categories': categories,
            'page_name': 'grievance_new',
            'error': kwargs.get('error', ''),
        }
        return request.render("oacis_grievance.portal_grievance_new", values)

    @http.route(['/my/grievance/submit'], type='http', auth="user", website=True, methods=['POST'])
    def portal_my_grievance_submit(self, **post):
        # Safe parsing: never let a malformed form become a 500.
        try:
            category_id = int(post.get('category_id') or 0)
        except (TypeError, ValueError):
            category_id = 0
        description = (post.get('description') or '').strip()

        error = None
        category = request.env['oacis.grievance.category'].browse(category_id) if category_id else None
        if not category or not category.exists():
            error = 'Please select a valid category.'
        elif not description:
            error = 'Please describe your grievance.'

        if error:
            return request.redirect('/my/grievance/new?error=%s' % error.replace(' ', '+'))

        request.env['oacis.grievance.request'].sudo().create({
            'category_id': category.id,
            'description': description,
            'raised_by_id': request.env.user.partner_id.id,
        })
        return request.redirect('/my/grievances')

    @http.route(['/my/grievance/<int:grievance_id>'], type='http', auth="user", website=True)
    def portal_my_grievance_detail(self, grievance_id, **kwargs):
        """Detail view so raisers can follow status and resolution."""
        grievance = request.env['oacis.grievance.request'].sudo().browse(grievance_id)
        if not grievance.exists() or grievance.raised_by_id != request.env.user.partner_id:
            raise NotFound(_('Grievance not found.'))
        values = {
            'grievance': grievance,
            'page_name': 'grievance',
        }
        return request.render('oacis_grievance.portal_grievance_detail', values)
