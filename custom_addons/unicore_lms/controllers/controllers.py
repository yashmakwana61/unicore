# from odoo import http


# class UnicoreLms(http.Controller):
#     @http.route('/unicore_lms/unicore_lms', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/unicore_lms/unicore_lms/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('unicore_lms.listing', {
#             'root': '/unicore_lms/unicore_lms',
#             'objects': http.request.env['unicore_lms.unicore_lms'].search([]),
#         })

#     @http.route('/unicore_lms/unicore_lms/objects/<model("unicore_lms.unicore_lms"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('unicore_lms.object', {
#             'object': obj
#         })
