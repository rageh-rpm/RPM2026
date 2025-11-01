# -*- coding: utf-8 -*-
# from odoo import http


# class Biotime8Integeration(http.Controller):
#     @http.route('/biotime8_integeration/biotime8_integeration', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/biotime8_integeration/biotime8_integeration/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('biotime8_integeration.listing', {
#             'root': '/biotime8_integeration/biotime8_integeration',
#             'objects': http.request.env['biotime8_integeration.biotime8_integeration'].search([]),
#         })

#     @http.route('/biotime8_integeration/biotime8_integeration/objects/<model("biotime8_integeration.biotime8_integeration"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('biotime8_integeration.object', {
#             'object': obj
#         })
