# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import json


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    overdraft_facility_id = fields.Many2one(
        'overdraft.facility',
        string='Overdraft Facility',
        compute='_compute_overdraft_facility',
        store=True,
        readonly=False,
        tracking=True
    )

    is_overdraft_payment = fields.Boolean(
        string='Is Overdraft Payment',
        related='journal_id.is_overdraft_facility',
        store=True
    )

    # Interest Calculation Fields
    actual_transaction_date = fields.Date(
        string='Actual Transaction Date',
        help='Date when transaction actually occurred (for interest calculation). If empty, uses payment date.'
    )

    interest_start_date = fields.Date(
        string='Interest Start Date',
        compute='_compute_interest_dates',
        store=True,
        help='Date from which interest starts accruing'
    )

    settlement_due_date = fields.Date(
        string='Settlement Due Date',
        compute='_compute_interest_dates',
        store=True,
        help='Expected settlement date based on facility due days'
    )

    total_interest_accrued = fields.Monetary(
        string='Total Interest Accrued',
        compute='_compute_payment_interest',
        store=True,
        currency_field='currency_id',
        help='Total interest accrued on this payment'
    )

    interest_accrual_ids = fields.One2many(
        'overdraft.interest.accrual',
        'payment_id',
        string='Interest Accruals'
    )

    # Settlement Tracking
    settlement_status = fields.Selection([
        ('pending', 'Pending Settlement'),
        ('partial', 'Partially Settled'),
        ('settled', 'Fully Settled')
    ], string='Settlement Status', default='pending', compute='_compute_settlement_status', store=True, tracking=True)

    amount_settled = fields.Monetary(
        string='Amount Settled',
        compute='_compute_settlement_amounts',
        store=True,
        currency_field='currency_id'
    )

    amount_outstanding = fields.Monetary(
        string='Outstanding Amount',
        compute='_compute_settlement_amounts',
        store=True,
        currency_field='currency_id'
    )

    settlement_allocation_ids = fields.One2many(
        'overdraft.settlement.allocation',
        'payment_id',
        string='Settlement Allocations'
    )

    @api.depends('journal_id', 'date', 'currency_id')
    def _compute_overdraft_facility(self):
        for payment in self:
            if payment.journal_id.is_overdraft_facility and payment.date and payment.currency_id:
                facility = self.env['overdraft.facility'].search([
                    ('journal_id', '=', payment.journal_id.id),
                    ('state', '=', 'active'),
                    ('date_from', '<=', payment.date),
                    ('date_to', '>=', payment.date),
                    ('currency_id', '=', payment.currency_id.id),
                ], limit=1)
                payment.overdraft_facility_id = facility
            else:
                payment.overdraft_facility_id = False

    @api.depends('overdraft_facility_id', 'date', 'actual_transaction_date',
                 'overdraft_facility_id.settlement_due_days')
    def _compute_interest_dates(self):
        for payment in self:
            if payment.overdraft_facility_id:
                payment.interest_start_date = payment.actual_transaction_date or payment.date
                if payment.interest_start_date and payment.overdraft_facility_id.settlement_due_days:
                    payment.settlement_due_date = payment.interest_start_date + timedelta(
                        days=payment.overdraft_facility_id.settlement_due_days
                    )
                else:
                    payment.settlement_due_date = False
            else:
                payment.interest_start_date = False
                payment.settlement_due_date = False

    @api.depends('interest_accrual_ids.interest_amount', 'interest_accrual_ids.state')
    def _compute_payment_interest(self):
        for payment in self:
            posted_interest = payment.interest_accrual_ids.filtered(lambda i: i.state == 'posted')
            payment.total_interest_accrued = sum(posted_interest.mapped('interest_amount'))

    @api.depends('settlement_allocation_ids.amount', 'settlement_allocation_ids.state', 'amount')
    def _compute_settlement_amounts(self):
        for payment in self:
            posted_allocations = payment.settlement_allocation_ids.filtered(
                lambda a: a.settlement_id.state == 'posted'
            )
            payment.amount_settled = sum(posted_allocations.mapped('amount'))
            payment.amount_outstanding = payment.amount - payment.amount_settled

    @api.depends('amount_settled', 'amount_outstanding')
    def _compute_settlement_status(self):
        for payment in self:
            if not payment.is_overdraft_payment or payment.state not in ['in_process', 'paid']:
                payment.settlement_status = 'pending'
            elif payment.amount_settled == 0:
                payment.settlement_status = 'pending'
            elif payment.amount_outstanding > 0.01:
                payment.settlement_status = 'partial'
            else:
                payment.settlement_status = 'settled'

    @api.constrains('overdraft_facility_id', 'amount', 'state')
    def _check_facility_limit(self):
        for payment in self:
            if payment.is_overdraft_payment and payment.overdraft_facility_id and payment.state in ['in_process', 'paid']:
                if payment.amount > payment.overdraft_facility_id.available_credit:
                    raise ValidationError(_(
                        'Payment exceeds available overdraft limit!\n'
                        'Available: %s\n'
                        'Payment amount: %s'
                    ) % (
                                              payment.overdraft_facility_id.available_credit,
                                              payment.amount
                                          ))

    def action_post(self):
        """Override to trigger interest accrual on posting"""
        res = super().action_post()

        for payment in self:
            if payment.is_overdraft_payment and payment.overdraft_facility_id:
                current_rate = payment.overdraft_facility_id.current_interest_rate
                if current_rate and current_rate > 0:
                    # Check if accrual already exists
                    existing = payment.interest_accrual_ids.filtered(lambda a: a.state == 'draft')
                    if not existing:
                        payment._create_interest_accrual()

        return res

    def _get_rate_periods_for_calculation(self, period_from, period_to):
        """
        Get list of rate periods with their rates for interest calculation
        Returns: list of dicts with from_date, to_date, rate, days
        """
        self.ensure_one()

        if not self.overdraft_facility_id:
            return []

        facility = self.overdraft_facility_id
        periods = []

        # Get all rate changes that affect this period
        rate_changes = self.env['overdraft.interest.rate.history'].search([
            ('facility_id', '=', facility.id),
            ('effective_date', '>=', period_from),
            ('effective_date', '<=', period_to)
        ], order='effective_date asc')

        current_date = period_from

        if not rate_changes:
            # No rate changes - use current rate for entire period
            days = (period_to - current_date).days + 1
            periods.append({
                'from_date': current_date,
                'to_date': period_to,
                'annual_rate': facility.current_interest_rate,
                'daily_rate': facility.current_interest_rate / 365 / 100,
                'days': days
            })
        else:
            # Process each rate change
            for idx, rate_change in enumerate(rate_changes):
                # Period before this rate change
                if current_date < rate_change.effective_date:
                    period_end = rate_change.effective_date - timedelta(days=1)

                    # Get the rate that was active before this change
                    prev_rate_record = self.env['overdraft.interest.rate.history'].search([
                        ('facility_id', '=', facility.id),
                        ('effective_date', '<', rate_change.effective_date)
                    ], order='effective_date desc', limit=1)

                    annual_rate = prev_rate_record.annual_interest_rate if prev_rate_record else facility.annual_interest_rate
                    days = (period_end - current_date).days + 1

                    if days > 0:
                        periods.append({
                            'from_date': current_date,
                            'to_date': period_end,
                            'annual_rate': annual_rate,
                            'daily_rate': annual_rate / 365 / 100,
                            'days': days
                        })

                    current_date = rate_change.effective_date

                # Period with the new rate
                if idx < len(rate_changes) - 1:
                    # Not the last rate change
                    period_end = rate_changes[idx + 1].effective_date - timedelta(days=1)
                else:
                    # Last rate change - goes until end of calculation period
                    period_end = period_to

                days = (period_end - current_date).days + 1
                if days > 0:
                    periods.append({
                        'from_date': current_date,
                        'to_date': period_end,
                        'annual_rate': rate_change.annual_interest_rate,
                        'daily_rate': rate_change.annual_interest_rate / 365 / 100,
                        'days': days
                    })

                current_date = period_end + timedelta(days=1)

        return periods

    def _calculate_interest_for_period(self, period_from, period_to, principal_amount=None):
        """
        Calculate interest for a specific period considering rate changes
        Returns: (total_interest, periods_breakdown)
        """
        self.ensure_one()

        if not period_from or not period_to or period_to < period_from:
            return 0.0, []

        if principal_amount is None:
            principal_amount = self.amount

        rate_periods = self._get_rate_periods_for_calculation(period_from, period_to)

        total_interest = 0.0
        breakdown = []

        for period in rate_periods:
            period_interest = principal_amount * period['daily_rate'] * period['days']
            total_interest += period_interest

            breakdown.append({
                'from': period['from_date'].strftime('%Y-%m-%d'),
                'to': period['to_date'].strftime('%Y-%m-%d'),
                'days': period['days'],
                'annual_rate': period['annual_rate'],
                'daily_rate': period['daily_rate'],
                'principal': principal_amount,
                'interest': round(period_interest, 2)
            })

        return round(total_interest, 2), breakdown

    def _create_interest_accrual(self):
        """Create interest accrual entry for this payment"""
        self.ensure_one()

        if not self.overdraft_facility_id:
            return False

        if not self.interest_start_date or not self.settlement_due_date:
            return False

        facility = self.overdraft_facility_id

        # Calculate interest with variable rates
        total_interest, periods_breakdown = self._calculate_interest_for_period(
            self.interest_start_date,
            self.settlement_due_date,
            self.amount
        )

        if total_interest == 0:
            return False

        total_days = (self.settlement_due_date - self.interest_start_date).days + 1

        accrual = self.env['overdraft.interest.accrual'].create({
            'facility_id': facility.id,
            'payment_id': self.id,
            'accrual_date': fields.Date.today(),
            'period_from': self.interest_start_date,
            'period_to': self.settlement_due_date,
            'principal_amount': self.amount,
            'daily_rate': facility.current_interest_rate / 365,
            'days_count': total_days,
            'interest_amount': total_interest,
            'period_breakdown': json.dumps(periods_breakdown, default=str),
            'state': 'draft',
        })

        self.message_post(
            body=_('Interest accrual created: %s for period %s to %s') % (
                accrual.name,
                self.interest_start_date,
                self.settlement_due_date
            )
        )

        return accrual

    def action_recalculate_interest(self):
        """Manually recalculate interest"""
        self.ensure_one()

        if not self.overdraft_facility_id:
            raise ValidationError(_('No overdraft facility assigned!'))

        # Delete draft interest accruals
        draft_accruals = self.interest_accrual_ids.filtered(lambda a: a.state == 'draft')
        if draft_accruals:
            draft_accruals.unlink()

        # Recreate interest accrual
        accrual = self._create_interest_accrual()

        if accrual:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Interest recalculated: %s') % accrual.interest_amount,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise ValidationError(_('Could not calculate interest. Check dates and rates.'))

    def action_view_interest_accruals(self):
        self.ensure_one()
        return {
            'name': _('Interest Accruals'),
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.interest.accrual',
            'view_mode': 'list,form',
            'domain': [('payment_id', '=', self.id)],
            'context': {
                'default_payment_id': self.id,
                'default_facility_id': self.overdraft_facility_id.id
            }
        }

    def action_view_settlement_allocations(self):
        self.ensure_one()
        return {
            'name': _('Settlement Allocations'),
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.settlement.allocation',
            'view_mode': 'list,form',
            'domain': [('payment_id', '=', self.id)],
            'context': {'default_payment_id': self.id}
        }
