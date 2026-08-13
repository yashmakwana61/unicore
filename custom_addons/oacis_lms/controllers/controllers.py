# from odoo import http


# class OacisLms(http.Controller):
#     @http.route('/oacis_lms/oacis_lms', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/oacis_lms/oacis_lms/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('oacis_lms.listing', {
#             'root': '/oacis_lms/oacis_lms',
#             'objects': http.request.env['oacis_lms.oacis_lms'].search([]),
#         })

#     @http.route('/oacis_lms/oacis_lms/objects/<model("oacis_lms.oacis_lms"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('oacis_lms.object', {
#             'object': obj
#         })
