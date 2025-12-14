# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TreasuryRequestRejectWizard(models.TransientModel):
    _name = 'treasury.request.reject.wizard'
    _description = 'Reject Payment Request'

    request_id = fields.Many2one(
        'treasury.request',
        string='Request',
        required=True,
        readonly=True
    )

    rejection_stage = fields.Char(
        string='Rejection Stage',
        readonly=True
    )

    rejection_reason = fields.Text(
        string='Rejection Reason',
        required=True
    )

    def action_confirm_reject(self):
        """Confirm rejection"""
        self.ensure_one()

        if not self.rejection_reason:
            raise UserError(_('Please provide a rejection reason.'))

        self.request_id.action_reject(self.rejection_reason)

        return {'type': 'ir.actions.act_window_close'}
