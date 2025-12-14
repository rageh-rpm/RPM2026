# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class OverdraftSettlement(models.Model):
    _name = 'overdraft.settlement'
    _description = 'Overdraft Settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'settlement_date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True
    )

    facility_id = fields.Many2one(
        'overdraft.facility',
        string='Overdraft Facility',
        required=True,
        domain="[('state', '=', 'active')]",
        tracking=True
    )

    settlement_date = fields.Date(
        string='Settlement Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )

    source_journal_id = fields.Many2one(
        'account.journal',
        string='Transfer From',
        required=True,
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        tracking=True
    )

    amount = fields.Monetary(
        string='Settlement Amount',
        required=True,
        currency_field='currency_id',
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        related='facility_id.company_id',
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='facility_id.currency_id',
        readonly=True
    )

    description = fields.Text(string='Description')

    # NEW: Payment Allocations
    allocation_ids = fields.One2many(
        'overdraft.settlement.allocation',
        'settlement_id',
        string='Payment Allocations'
    )

    total_allocated = fields.Monetary(
        string='Total Allocated',
        compute='_compute_allocated',
        store=True,
        currency_field='currency_id'
    )

    allocation_count = fields.Integer(
        string='# Payments',
        compute='_compute_allocated',
        store=True
    )

    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True, copy=False)

    @api.depends('allocation_ids.amount')
    def _compute_allocated(self):
        for settlement in self:
            settlement.total_allocated = sum(settlement.allocation_ids.mapped('amount'))
            settlement.allocation_count = len(settlement.allocation_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('overdraft.settlement') or _('New')
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for settlement in self:
            if settlement.amount <= 0:
                raise ValidationError(_('Settlement amount must be greater than zero!'))

            if settlement.amount > settlement.facility_id.current_outstanding:
                raise ValidationError(_(
                    'Settlement amount cannot exceed current outstanding!\n'
                    'Current outstanding: %s\n'
                    'Settlement amount: %s'
                ) % (
                                          settlement.facility_id.current_outstanding,
                                          settlement.amount
                                      ))

    @api.constrains('amount', 'total_allocated')
    def _check_allocation_total(self):
        for settlement in self:
            if settlement.state == 'draft' and settlement.allocation_ids:
                if abs(settlement.total_allocated - settlement.amount) > 0.01:  # Small tolerance
                    raise ValidationError(_(
                        'Total allocated amount (%(allocated)s) must equal settlement amount (%(amount)s)!'
                    ) % {
                                              'allocated': settlement.total_allocated,
                                              'amount': settlement.amount
                                          })

    def action_post(self):
        """Create journal entry for internal transfer (Odoo 18 style)"""
        for settlement in self:
            # Validate allocations exist
            if not settlement.allocation_ids:
                raise ValidationError(_('Please add at least one payment allocation!'))

            if abs(settlement.total_allocated - settlement.amount) > 0.01:
                raise ValidationError(_(
                    'Total allocated amount (%(allocated)s) must equal settlement amount (%(amount)s)!'
                ) % {
                                          'allocated': settlement.total_allocated,
                                          'amount': settlement.amount
                                      })

            # Prepare journal entry
            move_vals = {
                'move_type': 'entry',
                'date': settlement.settlement_date,
                'journal_id': settlement.source_journal_id.id,
                'ref': settlement.description or f'Overdraft Settlement: {settlement.name}',
                'line_ids': [
                    # Debit: Overdraft Account (reduce liability)
                    (0, 0, {
                        'name': f'Settlement: {settlement.name}',
                        'account_id': settlement.facility_id.journal_id.default_account_id.id,
                        'debit': settlement.amount,
                        'credit': 0.0,
                        'partner_id': False,
                    }),
                    # Credit: Source Bank Account
                    (0, 0, {
                        'name': f'Settlement: {settlement.name}',
                        'account_id': settlement.source_journal_id.default_account_id.id,
                        'debit': 0.0,
                        'credit': settlement.amount,
                        'partner_id': False,
                    }),
                ]
            }

            # Create and post journal entry
            move = self.env['account.move'].create(move_vals)
            move.action_post()

            settlement.write({
                'move_id': move.id,
                'state': 'posted'
            })

            settlement.message_post(body=_(
                'Settlement posted. Journal Entry: %s\nAllocated to %s payment(s)'
            ) % (move.name, settlement.allocation_count))

    def action_cancel(self):
        for settlement in self:
            if settlement.move_id and settlement.move_id.state == 'posted':
                raise ValidationError(_('Cannot cancel settlement with posted journal entry!'))
            settlement.state = 'cancelled'

    def action_set_to_draft(self):
        for settlement in self:
            if settlement.move_id:
                raise ValidationError(_('Cannot reset to draft. Journal entry already exists!'))
            settlement.state = 'draft'

    def action_view_journal_entry(self):
        """View related journal entry"""
        self.ensure_one()
        if not self.move_id:
            raise ValidationError(_('No journal entry found!'))

        return {
            'name': _('Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_allocations(self):
        """View payment allocations"""
        self.ensure_one()
        return {
            'name': _('Payment Allocations'),
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.settlement.allocation',
            'view_mode': 'list,form',
            'domain': [('settlement_id', '=', self.id)],
            'context': {'default_settlement_id': self.id}
        }
