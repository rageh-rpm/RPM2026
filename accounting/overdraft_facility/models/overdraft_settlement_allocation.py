# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class OverdraftSettlementAllocation(models.Model):
    _name = 'overdraft.settlement.allocation'
    _description = 'Settlement Payment Allocation'
    _order = 'settlement_id, payment_id'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True
    )

    settlement_id = fields.Many2one(
        'overdraft.settlement',
        string='Settlement',
        required=True,
        ondelete='cascade'
    )

    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        required=True,
        domain="[('overdraft_facility_id', '=', facility_id), ('state', 'in', ['posted', 'paid']), ('settlement_status', 'in', ['pending', 'partial'])]"
    )

    facility_id = fields.Many2one(
        'overdraft.facility',
        related='settlement_id.facility_id',
        store=True
    )

    payment_amount = fields.Monetary(
        string='Payment Amount',
        related='payment_id.amount',
        currency_field='currency_id'
    )

    payment_outstanding = fields.Monetary(
        string='Payment Outstanding',
        related='payment_id.amount_outstanding',
        currency_field='currency_id'
    )

    amount = fields.Monetary(
        string='Allocated Amount',
        required=True,
        currency_field='currency_id'
    )

    currency_id = fields.Many2one('res.currency', related='settlement_id.currency_id')
    state = fields.Selection(related='settlement_id.state', string='Status', store=True)

    payment_date = fields.Date(related='payment_id.date', string='Payment Date', store=True)
    settlement_due_date = fields.Date(related='payment_id.settlement_due_date', string='Due Date', store=True)
    payment_name = fields.Char(related='payment_id.name', string='Payment Ref', store=True)

    @api.depends('settlement_id.name', 'payment_id.name', 'amount')
    def _compute_name(self):
        for allocation in self:
            if allocation.settlement_id and allocation.payment_id:
                allocation.name = f"{allocation.settlement_id.name} → {allocation.payment_id.name} ({allocation.amount})"
            else:
                allocation.name = _('New Allocation')

    @api.constrains('amount', 'payment_id')
    def _check_amount(self):
        for allocation in self:
            if allocation.amount <= 0:
                raise ValidationError(_('Allocation amount must be greater than zero!'))

            if allocation.amount > allocation.payment_outstanding:
                raise ValidationError(_(
                    'Allocation amount (%(amount)s) cannot exceed payment outstanding (%(outstanding)s)!'
                ) % {
                                          'amount': allocation.amount,
                                          'outstanding': allocation.payment_outstanding
                                      })

    @api.onchange('payment_id')
    def _onchange_payment_id(self):
        """Auto-fill amount with payment outstanding"""
        if self.payment_id:
            self.amount = self.payment_id.amount_outstanding
