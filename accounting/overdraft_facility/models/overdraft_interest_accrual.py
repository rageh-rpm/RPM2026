# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class OverdraftInterestAccrual(models.Model):
    _name = 'overdraft.interest.accrual'
    _description = 'Overdraft Interest Accrual'
    _order = 'accrual_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    facility_id = fields.Many2one(
        'overdraft.facility',
        string='Facility',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    accrual_date = fields.Date(
        string='Accrual Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )

    period_from = fields.Date(
        string='Period From',
        required=True
    )

    period_to = fields.Date(
        string='Period To',
        required=True
    )

    days_count = fields.Integer(
        string='Number of Days',
        compute='_compute_days',
        store=True
    )

    principal_amount = fields.Monetary(
        string='Principal Amount',
        required=True,
        currency_field='currency_id',
        help='Payment amount on which interest is calculated'
    )

    daily_rate = fields.Float(
        string='Daily Rate (%)',
        required=True,
        digits=(8, 6),
        help='Daily interest rate'
    )

    interest_amount = fields.Monetary(
        string='Interest Amount',
        required=True,
        currency_field='currency_id',
        tracking=True
    )

    # NEW: Store detailed breakdown when rates change
    period_breakdown = fields.Text(
        string='Rate Period Breakdown',
        help='JSON string containing detailed calculation for variable rates'
    )

    has_variable_rates = fields.Boolean(
        string='Has Variable Rates',
        compute='_compute_has_variable_rates',
        store=True
    )

    currency_id = fields.Many2one('res.currency', related='facility_id.currency_id')
    company_id = fields.Many2one('res.company', related='facility_id.company_id')

    # Accounting
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

    notes = fields.Text(string='Notes')

    @api.depends('period_from', 'period_to')
    def _compute_days(self):
        for line in self:
            if line.period_from and line.period_to:
                line.days_count = (line.period_to - line.period_from).days + 1
            else:
                line.days_count = 0

    @api.depends('period_breakdown')
    def _compute_has_variable_rates(self):
        for line in self:
            if line.period_breakdown:
                try:
                    periods = json.loads(line.period_breakdown)
                    line.has_variable_rates = len(periods) > 1
                except:
                    line.has_variable_rates = False
            else:
                line.has_variable_rates = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('overdraft.interest.accrual') or _('New')
        return super().create(vals_list)

    def action_post(self):
        """Create journal entry for interest accrual - COMPLETELY FIXED"""
        for accrual in self:
            facility = accrual.facility_id

            # Validate configuration
            if not facility.interest_journal_id:
                raise ValidationError(_('Interest Journal not configured on facility!'))
            if not facility.interest_expense_account_id:
                raise ValidationError(_('Interest Expense Account not configured on facility!'))
            if not facility.interest_payable_account_id:
                raise ValidationError(_('Interest Payable Account not configured on facility!'))

            # ✅ THE KEY: Never set currency_id on move lines in Odoo 18
            # The journal's currency is inherited automatically

            # Create journal entry
            move_vals = {
                'move_type': 'entry',
                'date': accrual.accrual_date,
                'journal_id': facility.interest_journal_id.id,
                'ref': f'Interest Accrual: {accrual.name} - Payment: {accrual.payment_id.name}',
                'line_ids': [
                    # Debit: Interest Expense
                    (0, 0, {
                        'name': f'Interest on {accrual.payment_id.name}',
                        'account_id': facility.interest_expense_account_id.id,
                        'debit': accrual.interest_amount,  # ✅ Use debit, NOT amount_currency
                        'credit': 0.0,
                        # ✅ DO NOT SET currency_id here!
                    }),
                    # Credit: Interest Payable
                    (0, 0, {
                        'name': f'Interest on {accrual.payment_id.name}',
                        'account_id': facility.interest_payable_account_id.id,
                        'debit': 0.0,
                        'credit': accrual.interest_amount,  # ✅ Use credit, NOT amount_currency
                        # ✅ DO NOT SET currency_id here!
                    }),
                ]
            }

            # Create and post journal entry
            move = self.env['account.move'].create(move_vals)

            try:
                move.action_post()

                accrual.write({
                    'move_id': move.id,
                    'state': 'posted'
                })

                accrual.message_post(body=_(
                    'Interest accrual posted. Journal Entry: %s<br/>Amount: %s %s'
                ) % (move.name, accrual.interest_amount, accrual.currency_id.symbol))

            except Exception as e:
                # If posting fails, delete the move and raise error
                move.unlink()
                raise ValidationError(_('Failed to post journal entry: %s') % str(e))

    def action_cancel(self):
        for accrual in self:
            if accrual.move_id and accrual.move_id.state == 'posted':
                raise ValidationError(_('Cannot cancel accrual with posted journal entry!'))
            accrual.state = 'cancelled'

    def action_set_to_draft(self):
        for accrual in self:
            if accrual.move_id:
                raise ValidationError(_('Cannot reset to draft. Journal entry exists!'))
            accrual.state = 'draft'

    def action_post_batch(self):
        """Post multiple interest accruals at once"""
        draft_accruals = self.filtered(lambda a: a.state == 'draft')

        if not draft_accruals:
            raise ValidationError(_('No draft accruals selected!'))

        posted_count = 0
        failed_count = 0
        errors = []

        for accrual in draft_accruals:
            try:
                accrual.action_post()
                posted_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"{accrual.name}: {str(e)}")

        # Show summary notification
        message = _('Posted: %s\nFailed: %s') % (posted_count, failed_count)

        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors[:5])  # Show first 5 errors

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Posting Complete'),
                'message': message,
                'type': 'success' if failed_count == 0 else 'warning',
                'sticky': True,
            }
        }

    def action_view_journal_entry(self):
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

    def action_view_breakdown(self):
        """View detailed rate breakdown for variable rates"""
        self.ensure_one()

        if not self.period_breakdown:
            raise ValidationError(_('No breakdown data available!'))

        try:
            periods = json.loads(self.period_breakdown)
            breakdown_html = "<table class='table table-sm'>"
            breakdown_html += "<tr><th>Period</th><th>Days</th><th>Rate</th><th>Interest</th></tr>"

            for period in periods:
                breakdown_html += f"<tr>"
                breakdown_html += f"<td>{period['from']} to {period['to']}</td>"
                breakdown_html += f"<td>{period['days']}</td>"
                breakdown_html += f"<td>{period['annual_rate']:.2f}%</td>"
                breakdown_html += f"<td>{period['interest']:.2f}</td>"
                breakdown_html += f"</tr>"

            breakdown_html += "</table>"

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Interest Rate Breakdown'),
                    'message': breakdown_html,
                    'type': 'info',
                    'sticky': True,
                }
            }
        except:
            raise ValidationError(_('Error parsing breakdown data!'))
