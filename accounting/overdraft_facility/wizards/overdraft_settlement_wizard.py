# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class OverdraftSettlementWizard(models.TransientModel):
    _name = 'overdraft.settlement.wizard'
    _description = 'Create Settlement from Due Payments'

    facility_id = fields.Many2one('overdraft.facility', string='Facility', required=True, readonly=True)
    facility_name = fields.Char(related='facility_id.name', string='Facility Reference')
    settlement_date = fields.Date(string='Settlement Date', required=True, default=fields.Date.today)
    source_journal_id = fields.Many2one(
        'account.journal',
        string='Transfer From',
        required=True,
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]"
    )
    company_id = fields.Many2one('res.company', related='facility_id.company_id')
    currency_id = fields.Many2one('res.currency', related='facility_id.currency_id')
    description = fields.Text(string='Description')

    line_ids = fields.One2many(
        'overdraft.settlement.wizard.line',
        'wizard_id',
        string='Payments to Settle'
    )

    total_selected = fields.Monetary(
        string='Total Selected',
        compute='_compute_totals',
        currency_field='currency_id'
    )

    selected_count = fields.Integer(
        string='Selected Payments',
        compute='_compute_totals'
    )

    @api.depends('line_ids.selected', 'line_ids.amount_to_settle')
    def _compute_totals(self):
        for wizard in self:
            selected_lines = wizard.line_ids.filtered('selected')
            wizard.total_selected = sum(selected_lines.mapped('amount_to_settle'))
            wizard.selected_count = len(selected_lines)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        if 'facility_id' in self._context:
            facility_id = self._context['facility_id']

            # Get all pending/partial payments
            payments = self.env['account.payment'].search([
                ('overdraft_facility_id', '=', facility_id),
                ('state', 'in', ['posted', 'paid']),
                ('settlement_status', 'in', ['pending', 'partial'])
            ], order='settlement_due_date, date')

            lines = []
            for payment in payments:
                lines.append((0, 0, {
                    'payment_id': payment.id,
                    'amount_to_settle': payment.amount_outstanding,
                    'selected': False
                }))

            res['line_ids'] = lines

        return res

    def action_select_all(self):
        """Select all payments"""
        self.ensure_one()
        self.line_ids.write({'selected': True})
        return {'type': 'ir.actions.do_nothing'}

    def action_deselect_all(self):
        """Deselect all payments"""
        self.ensure_one()
        self.line_ids.write({'selected': False})
        return {'type': 'ir.actions.do_nothing'}

    def action_select_overdue(self):
        """Select only overdue payments"""
        self.ensure_one()
        today = fields.Date.today()
        for line in self.line_ids:
            line.selected = line.settlement_due_date and line.settlement_due_date < today
        return {'type': 'ir.actions.do_nothing'}

    def action_create_settlement(self):
        self.ensure_one()

        selected_lines = self.line_ids.filtered('selected')

        if not selected_lines:
            raise ValidationError(_('Please select at least one payment!'))

        # Create settlement
        settlement = self.env['overdraft.settlement'].create({
            'facility_id': self.facility_id.id,
            'settlement_date': self.settlement_date,
            'source_journal_id': self.source_journal_id.id,
            'amount': self.total_selected,
            'description': self.description or f'Settlement for {self.selected_count} payment(s)',
        })

        # Create allocations
        for line in selected_lines:
            self.env['overdraft.settlement.allocation'].create({
                'settlement_id': settlement.id,
                'payment_id': line.payment_id.id,
                'amount': line.amount_to_settle,
            })

        return {
            'name': _('Settlement'),
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.settlement',
            'res_id': settlement.id,
            'view_mode': 'form',
            'target': 'current',
        }


class OverdraftSettlementWizardLine(models.TransientModel):
    _name = 'overdraft.settlement.wizard.line'
    _description = 'Settlement Wizard Line'
    _order = 'settlement_due_date, payment_date'

    wizard_id = fields.Many2one('overdraft.settlement.wizard', required=True, ondelete='cascade')

    selected = fields.Boolean(string='Select', default=False)

    payment_id = fields.Many2one('account.payment', string='Payment', required=True, readonly=True)
    payment_name = fields.Char(related='payment_id.name', string='Payment Ref', readonly=True)
    payment_date = fields.Date(related='payment_id.date', string='Payment Date', readonly=True)
    settlement_due_date = fields.Date(related='payment_id.settlement_due_date', string='Due Date', readonly=True)

    payment_amount = fields.Monetary(
        related='payment_id.amount',
        string='Payment Amount',
        currency_field='currency_id',
        readonly=True
    )

    amount_settled = fields.Monetary(
        related='payment_id.amount_settled',
        string='Already Settled',
        currency_field='currency_id',
        readonly=True
    )

    amount_outstanding = fields.Monetary(
        related='payment_id.amount_outstanding',
        string='Outstanding',
        currency_field='currency_id',
        readonly=True
    )

    amount_to_settle = fields.Monetary(
        string='Amount to Settle',
        required=True,
        currency_field='currency_id'
    )

    currency_id = fields.Many2one('res.currency', related='wizard_id.currency_id', readonly=True)

    days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_days_overdue',
        store=True
    )

    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_days_overdue',
        store=True
    )

    @api.depends('settlement_due_date')
    def _compute_days_overdue(self):
        today = fields.Date.today()
        for line in self:
            if line.settlement_due_date:
                delta = (today - line.settlement_due_date).days
                line.days_overdue = max(0, delta)
                line.is_overdue = delta > 0
            else:
                line.days_overdue = 0
                line.is_overdue = False

    @api.constrains('amount_to_settle', 'amount_outstanding')
    def _check_amount(self):
        for line in self:
            if line.selected and line.amount_to_settle > line.amount_outstanding:
                raise ValidationError(_(
                    'Amount to settle cannot exceed outstanding amount for payment %s!'
                ) % line.payment_name)
