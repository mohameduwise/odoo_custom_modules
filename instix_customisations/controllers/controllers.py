# from odoo import http


# class InstixCustomisations(http.Controller):
#     @http.route('/instix_customisations/instix_customisations', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/instix_customisations/instix_customisations/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('instix_customisations.listing', {
#             'root': '/instix_customisations/instix_customisations',
#             'objects': http.request.env['instix_customisations.instix_customisations'].search([]),
#         })

#     @http.route('/instix_customisations/instix_customisations/objects/<model("instix_customisations.instix_customisations"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('instix_customisations.object', {
#             'object': obj
#         })

