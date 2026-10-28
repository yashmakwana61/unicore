# from odoo import http


# class EdicaiLms(http.Controller):
#     @http.route('/edicai_lms/edicai_lms', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/edicai_lms/edicai_lms/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('edicai_lms.listing', {
#             'root': '/edicai_lms/edicai_lms',
#             'objects': http.request.env['edicai_lms.edicai_lms'].search([]),
#         })

#     @http.route('/edicai_lms/edicai_lms/objects/<model("edicai_lms.edicai_lms"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('edicai_lms.object', {
#             'object': obj
#         })
