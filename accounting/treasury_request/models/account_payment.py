# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    treasury_request_id = fields.Many2one(
        'treasury.request',
        string='Treasury Request',
        readonly=True,
        copy=False,
        ondelete='restrict'
    )

    def action_view_treasury_request(self):
        """View related treasury request"""
        self.ensure_one()

        if not self.treasury_request_id:
            return {}

        return {
            'name': _('Treasury Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'treasury.request',
            'res_id': self.treasury_request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
