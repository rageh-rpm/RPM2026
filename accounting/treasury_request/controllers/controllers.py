# -*- coding: utf-8 -*-
# from odoo import http


# class DigitsTreasuryWorkflow(http.Controller):
#     @http.route('/digits_treasury_workflow/digits_treasury_workflow', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/digits_treasury_workflow/digits_treasury_workflow/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('digits_treasury_workflow.listing', {
#             'root': '/digits_treasury_workflow/digits_treasury_workflow',
#             'objects': http.request.env['digits_treasury_workflow.digits_treasury_workflow'].search([]),
#         })

#     @http.route('/digits_treasury_workflow/digits_treasury_workflow/objects/<model("digits_treasury_workflow.digits_treasury_workflow"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('digits_treasury_workflow.object', {
#             'object': obj
#         })

