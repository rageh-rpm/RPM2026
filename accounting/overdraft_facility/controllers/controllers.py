# -*- coding: utf-8 -*-
# from odoo import http


# class OverdraftPayment(http.Controller):
#     @http.route('/overdraft_payment/overdraft_payment', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/overdraft_payment/overdraft_payment/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('overdraft_payment.listing', {
#             'root': '/overdraft_payment/overdraft_payment',
#             'objects': http.request.env['overdraft_payment.overdraft_payment'].search([]),
#         })

#     @http.route('/overdraft_payment/overdraft_payment/objects/<model("overdraft_payment.overdraft_payment"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('overdraft_payment.object', {
#             'object': obj
#         })

