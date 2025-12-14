# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class OverdraftFacility(models.Model):
    _name = 'overdraft.facility'
    _description = 'Overdraft Facility'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Facility Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Overdraft Account',
        required=True,
        domain="[('type', '=', 'bank'), ('is_overdraft_facility', '=', True)]",
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        related='journal_id.company_id',
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Facility Currency',
        required=True,
        tracking=True,
        help='Currency for this overdraft facility'
    )

    # Period
    date_from = fields.Date(
        string='Start Date',
        required=True,
        tracking=True
    )

    date_to = fields.Date(
        string='End Date',
        required=True,
        tracking=True
    )

    days_count = fields.Integer(
        string='Duration (Days)',
        compute='_compute_days_count',
        store=True
    )

    # Credit Limit
    credit_limit = fields.Monetary(
        string='Credit Limit',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help='Maximum credit limit approved'
    )

    # ============ Interest Configuration ============

    settlement_due_days = fields.Integer(
        string='Settlement Due (Days)',
        required=True,
        default=30,
        tracking=True,
        help='Number of days from payment date to settlement due date'
    )

    annual_interest_rate = fields.Float(
        string='Initial Annual Interest Rate (%)',
        digits=(5, 2),
        tracking=True,
        help='Initial annual interest rate percentage for daily calculation'
    )

    daily_interest_rate = fields.Float(
        string='Daily Interest Rate (%)',
        compute='_compute_daily_rate',
        store=True,
        digits=(8, 6),
        help='Daily rate = Annual Rate / 365'
    )

    # NEW: Interest Rate History
    interest_rate_history_ids = fields.One2many(
        'overdraft.interest.rate.history',
        'facility_id',
        string='Interest Rate History'
    )

    current_interest_rate = fields.Float(
        string='Current Interest Rate (%)',
        compute='_compute_current_rate',
        store=True,
        digits=(5, 2),
        help='Most recent active interest rate'
    )

    rate_change_count = fields.Integer(
        string='Rate Changes',
        compute='_compute_rate_change_count'
    )

    # Interest Accounting Configuration
    interest_journal_id = fields.Many2one(
        'account.journal',
        string='Interest Journal',
        domain="[('type', '=', 'general')]",
        tracking=True,
        help='Journal for interest accrual entries'
    )

    interest_expense_account_id = fields.Many2one(
        'account.account',
        string='Interest Expense Account',
        domain="[('account_type', 'in', ['expense', 'expense_direct_cost'])]",
        tracking=True,
        help='Debit account for interest expense'
    )

    interest_payable_account_id = fields.Many2one(
        'account.account',
        string='Interest Payable Account',
        domain="[('account_type', '=', 'liability_current')]",
        tracking=True,
        help='Credit account for accrued interest (liability)'
    )

    # Interest Totals
    total_interest_accrued = fields.Monetary(
        string='Total Interest Accrued',
        compute='_compute_interest_totals',
        store=True,
        currency_field='currency_id',
        help='Total interest calculated and posted'
    )

    total_interest_entries = fields.Integer(
        string='Interest Entries Count',
        compute='_compute_interest_totals',
        store=True
    )

    # Payment Status Breakdown
    total_paid_payments = fields.Monetary(
        string='Paid Payments',
        compute='_compute_facility_usage',
        store=True,
        currency_field='currency_id',
        help='Total amount of PAID payments'
    )

    paid_payment_count = fields.Integer(
        string='# Paid Payments',
        compute='_compute_facility_usage',
        store=True
    )

    total_in_process_payments = fields.Monetary(
        string='In Process Payments',
        compute='_compute_facility_usage',
        store=True,
        currency_field='currency_id',
        help='Total amount of IN PROCESS payments'
    )

    in_process_payment_count = fields.Integer(
        string='# In Process',
        compute='_compute_facility_usage',
        store=True
    )

    total_payments = fields.Monetary(
        string='Total Payments',
        compute='_compute_facility_usage',
        store=True,
        currency_field='currency_id',
        help='Total payments (Paid + In Process)'
    )

    payment_count = fields.Integer(
        string='Total # of Payments',
        compute='_compute_facility_usage',
        store=True
    )

    # NEW: Pending Settlements Count
    pending_settlement_count = fields.Integer(
        string='Pending Settlements',
        compute='_compute_pending_settlements'
    )

    # Settlements
    total_settlements = fields.Monetary(
        string='Total Settlements',
        compute='_compute_facility_usage',
        store=True,
        currency_field='currency_id',
        help='Total amount settled/repaid to facility'
    )

    settlement_count = fields.Integer(
        string='Number of Settlements',
        compute='_compute_facility_usage',
        store=True
    )

    # Current Balance
    current_outstanding = fields.Monetary(
        string='Current Outstanding',
        compute='_compute_facility_usage',
        store=True,
        currency_field='currency_id',
        help='Net amount currently owed = Payments - Settlements'
    )

    available_credit = fields.Monetary(
        string='Available Credit',
        compute='_compute_facility_usage',
        store=True,
        currency_field='currency_id',
        help='Remaining credit = Credit Limit - Outstanding'
    )

    utilization_percentage = fields.Float(
        string='Utilization %',
        compute='_compute_facility_usage',
        store=True,
        digits=(5, 2),
        help='Percentage of credit limit used'
    )

    utilization_amount = fields.Monetary(
        string='Utilized Amount',
        compute='_compute_facility_usage',
        store=True,
        currency_field='currency_id',
        help='Same as Current Outstanding'
    )

    # Relations
    payment_ids = fields.One2many(
        'account.payment',
        'overdraft_facility_id',
        string='Payments'
    )

    settlement_ids = fields.One2many(
        'overdraft.settlement',
        'facility_id',
        string='Settlements'
    )

    interest_line_ids = fields.One2many(
        'overdraft.interest.accrual',
        'facility_id',
        string='Interest Accruals'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True, copy=False)

    notes = fields.Text(string='Notes')
    color = fields.Integer(string='Color Index')

    # ============ Compute Methods ============

    @api.depends('date_from', 'date_to')
    def _compute_days_count(self):
        for facility in self:
            if facility.date_from and facility.date_to:
                facility.days_count = (facility.date_to - facility.date_from).days + 1
            else:
                facility.days_count = 0

    @api.depends('annual_interest_rate')
    def _compute_daily_rate(self):
        for facility in self:
            if facility.annual_interest_rate:
                facility.daily_interest_rate = facility.annual_interest_rate / 365
            else:
                facility.daily_interest_rate = 0.0

    @api.depends('interest_rate_history_ids.effective_date', 'interest_rate_history_ids.annual_interest_rate')
    def _compute_current_rate(self):
        """Get the most recent active rate"""
        today = fields.Date.today()
        for facility in self:
            rate_history = facility.interest_rate_history_ids.filtered(
                lambda r: r.effective_date <= today
            ).sorted('effective_date', reverse=True)

            if rate_history:
                facility.current_interest_rate = rate_history[0].annual_interest_rate
            else:
                facility.current_interest_rate = facility.annual_interest_rate

    @api.depends('interest_rate_history_ids')
    def _compute_rate_change_count(self):
        for facility in self:
            facility.rate_change_count = len(facility.interest_rate_history_ids)

    @api.depends('payment_ids.settlement_status')
    def _compute_pending_settlements(self):
        for facility in self:
            facility.pending_settlement_count = len(
                facility.payment_ids.filtered(
                    lambda p: p.settlement_status in ['pending', 'partial'] and p.state in ['posted', 'paid']
                )
            )

    @api.depends('interest_line_ids.interest_amount', 'interest_line_ids.state')
    def _compute_interest_totals(self):
        for facility in self:
            posted_interest = facility.interest_line_ids.filtered(lambda l: l.state == 'posted')
            facility.total_interest_accrued = sum(posted_interest.mapped('interest_amount'))
            facility.total_interest_entries = len(posted_interest)

    @api.depends(
        'payment_ids.amount',
        'payment_ids.state',
        'settlement_ids.amount',
        'settlement_ids.state',
        'credit_limit',
        'currency_id'
    )
    def _compute_facility_usage(self):
        for facility in self:
            all_payments = facility.payment_ids

            paid_payments = all_payments.filtered(lambda p: p.state == 'paid')
            facility.total_paid_payments = sum(paid_payments.mapped('amount'))
            facility.paid_payment_count = len(paid_payments)

            in_process_payments = all_payments.filtered(lambda p: p.state == 'in_process')
            facility.total_in_process_payments = sum(in_process_payments.mapped('amount'))
            facility.in_process_payment_count = len(in_process_payments)

            posted_payments = paid_payments + in_process_payments
            total_payments = sum(posted_payments.mapped('amount'))
            facility.total_payments = total_payments
            facility.payment_count = len(posted_payments)

            posted_settlements = facility.settlement_ids.filtered(
                lambda s: s.state == 'posted' and s.currency_id == facility.currency_id
            )
            total_settlements = sum(posted_settlements.mapped('amount'))
            facility.total_settlements = total_settlements
            facility.settlement_count = len(posted_settlements)

            outstanding = total_payments - total_settlements
            facility.current_outstanding = outstanding
            facility.utilization_amount = outstanding
            facility.available_credit = facility.credit_limit - outstanding

            if facility.credit_limit > 0:
                facility.utilization_percentage = (outstanding / facility.credit_limit) * 100
            else:
                facility.utilization_percentage = 0.0

    # ============ ORM Methods ============

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('overdraft.facility') or _('New')
        return super().create(vals_list)

    # ============ Constraints ============

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for facility in self:
            if facility.date_from >= facility.date_to:
                raise ValidationError(_('End date must be after start date!'))

    @api.constrains('credit_limit')
    def _check_credit_limit(self):
        for facility in self:
            if facility.credit_limit <= 0:
                raise ValidationError(_('Credit limit must be greater than zero!'))

    @api.constrains('settlement_due_days')
    def _check_settlement_days(self):
        for facility in self:
            if facility.settlement_due_days <= 0:
                raise ValidationError(_('Settlement due days must be greater than zero!'))

    @api.constrains('journal_id', 'currency_id', 'date_from', 'date_to', 'state')
    def _check_overlap(self):
        for facility in self:
            if facility.state in ['draft', 'cancelled']:
                continue

            overlapping = self.search([
                ('id', '!=', facility.id),
                ('journal_id', '=', facility.journal_id.id),
                ('currency_id', '=', facility.currency_id.id),
                ('state', '=', 'active'),
                '|',
                '&', ('date_from', '<=', facility.date_from), ('date_to', '>=', facility.date_from),
                '&', ('date_from', '<=', facility.date_to), ('date_to', '>=', facility.date_to),
            ])

            if overlapping:
                raise ValidationError(_(
                    'Overlapping facility detected!\n'
                    'Facility %s already exists for this account in the same currency (%s) and period.'
                ) % (overlapping[0].name, facility.currency_id.name))

    @api.constrains('annual_interest_rate')
    def _check_interest_rate(self):
        for facility in self:
            if facility.annual_interest_rate < 0 or facility.annual_interest_rate > 100:
                raise ValidationError(_('Interest rate must be between 0 and 100!'))

    # ============ Actions ============

    def action_activate(self):
        for facility in self:
            # Validate interest configuration
            if facility.annual_interest_rate > 0:
                if not facility.interest_journal_id:
                    raise ValidationError(_('Interest Journal is required when interest rate is set!'))
                if not facility.interest_expense_account_id:
                    raise ValidationError(_('Interest Expense Account is required!'))
                if not facility.interest_payable_account_id:
                    raise ValidationError(_('Interest Payable Account is required!'))

            facility.state = 'active'
            facility.message_post(body=_('Facility activated'))

    def action_close(self):
        for facility in self:
            if facility.current_outstanding > 0:
                raise ValidationError(_(
                    'Cannot close facility with outstanding balance!\n'
                    'Current balance: %s %s\n'
                    'Please settle the balance first.'
                ) % (facility.current_outstanding, facility.currency_id.name))

            facility.state = 'closed'
            facility.message_post(body=_('Facility closed'))

    def action_cancel(self):
        for facility in self:
            if facility.payment_ids or facility.settlement_ids:
                raise ValidationError(_('Cannot cancel facility with linked transactions!'))
            facility.state = 'cancelled'

    def action_generate_monthly_interest_accruals(self):
        """
        Generate monthly interest accruals for all active facilities
        Called by scheduled action at month end
        """
        today = fields.Date.today()

        # Only run on last 3 days of month
        if today.day < 28:
            return 0

        facilities = self.search([
            ('state', '=', 'active'),
            ('current_interest_rate', '>', 0)
        ])

        total_created = 0

        for facility in facilities:
            # Get unsettled payments
            payments = facility.payment_ids.filtered(
                lambda p: p.settlement_status in ['pending', 'partial']
                          and p.state in ['posted', 'paid']
                          and p.interest_start_date
                          and p.interest_start_date <= today
            )

            for payment in payments:
                # Find last posted accrual
                last_accrual = self.env['overdraft.interest.accrual'].search([
                    ('payment_id', '=', payment.id),
                    ('state', '=', 'posted')
                ], order='period_to desc', limit=1)

                if last_accrual:
                    # Create accrual from day after last accrual to today
                    period_from = last_accrual.period_to + timedelta(days=1)
                else:
                    # No accrual yet - check if draft exists
                    draft_accrual = self.env['overdraft.interest.accrual'].search([
                        ('payment_id', '=', payment.id),
                        ('state', '=', 'draft')
                    ], limit=1)

                    if draft_accrual:
                        # Auto-post the draft
                        try:
                            draft_accrual.action_post()
                            total_created += 1
                        except:
                            pass
                    continue

                period_to = min(today, payment.settlement_due_date or today)

                # Only create if period is at least 1 day
                if period_to <= period_from:
                    continue

                # Calculate interest
                total_interest, breakdown = payment._calculate_interest_for_period(
                    period_from,
                    period_to,
                    payment.amount_outstanding
                )

                if total_interest > 0:
                    days = (period_to - period_from).days + 1

                    accrual = self.env['overdraft.interest.accrual'].create({
                        'facility_id': facility.id,
                        'payment_id': payment.id,
                        'accrual_date': today,
                        'period_from': period_from,
                        'period_to': period_to,
                        'principal_amount': payment.amount_outstanding,
                        'daily_rate': facility.current_interest_rate / 365,
                        'days_count': days,
                        'interest_amount': total_interest,
                        'period_breakdown': json.dumps(breakdown, default=str),
                        'state': 'draft',
                        'notes': f'Monthly accrual - Auto-generated'
                    })

                    # Auto-post monthly accruals
                    try:
                        accrual.action_post()
                        total_created += 1
                    except Exception as e:
                        # Log error but continue
                        accrual.message_post(body=f'Failed to post: {str(e)}')

        return total_created


    def _should_create_monthly_accrual(self, payment, accrual_date):
        """Check if monthly accrual should be created for this payment"""
        # Get last accrual date for this payment
        last_accrual = self.env['overdraft.interest.accrual'].search([
            ('payment_id', '=', payment.id),
            ('state', '=', 'posted')
        ], order='period_to desc', limit=1)

        if not last_accrual:
            # No previous accrual, check if we're at month end
            return accrual_date.day >= 28  # Last few days of month

        # Check if a month has passed since last accrual
        from dateutil.relativedelta import relativedelta
        next_accrual_date = last_accrual.period_to + relativedelta(months=1)

        return accrual_date >= next_accrual_date

    def _create_monthly_interest_accrual(self, payment, accrual_date):
        """Create monthly interest accrual for a payment"""
        # Determine period
        last_accrual = self.env['overdraft.interest.accrual'].search([
            ('payment_id', '=', payment.id),
            ('state', '=', 'posted')
        ], order='period_to desc', limit=1)

        if last_accrual:
            # Continue from last accrual
            from datetime import timedelta
            period_from = last_accrual.period_to + timedelta(days=1)
        else:
            # First accrual - start from interest start date
            period_from = payment.interest_start_date

        # Period to = end of current month or settlement due date (whichever is earlier)
        from dateutil.relativedelta import relativedelta
        period_to = (period_from + relativedelta(day=31))

        if payment.settlement_due_date and period_to > payment.settlement_due_date:
            period_to = payment.settlement_due_date

        # Don't create if period already covered
        if period_to <= period_from:
            return False

        # Calculate interest with variable rates
        total_interest, periods = payment._calculate_interest_for_period(period_from, period_to)

        if total_interest == 0:
            return False

        # Create accrual
        days = (period_to - period_from).days + 1

        accrual = self.env['overdraft.interest.accrual'].create({
            'facility_id': self.id,
            'payment_id': payment.id,
            'accrual_date': accrual_date,
            'period_from': period_from,
            'period_to': period_to,
            'principal_amount': payment.amount_outstanding,  # Use outstanding, not full amount
            'daily_rate': self.current_interest_rate / 365,
            'days_count': days,
            'interest_amount': total_interest,
            'period_breakdown': json.dumps(periods) if periods else False,
            'state': 'draft',
            'notes': f'Monthly accrual for {period_from} to {period_to}'
        })

        # Auto-post monthly accruals
        accrual.action_post()

        return accrual

    def action_view_payments(self):
        self.ensure_one()
        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('overdraft_facility_id', '=', self.id)],
            'context': {'default_overdraft_facility_id': self.id}
        }

    def action_view_settlements(self):
        self.ensure_one()
        return {
            'name': _('Settlements'),
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.settlement',
            'view_mode': 'list,form',
            'domain': [('facility_id', '=', self.id)],
            'context': {'default_facility_id': self.id}
        }

    def action_view_interest_accruals(self):
        self.ensure_one()
        return {
            'name': _('Interest Accruals'),
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.interest.accrual',
            'view_mode': 'list,form',
            'domain': [('facility_id', '=', self.id)],
            'context': {'default_facility_id': self.id}
        }

    def action_change_interest_rate(self):
        """Open wizard to change interest rate"""
        self.ensure_one()
        return {
            'name': _('Change Interest Rate'),
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.rate.change.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_facility_id': self.id,
                'default_current_rate': self.current_interest_rate,
            }
        }

    def action_view_rate_history(self):
        """View interest rate change history"""
        self.ensure_one()
        return {
            'name': _('Interest Rate History'),
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.interest.rate.history',
            'view_mode': 'list,form',
            'domain': [('facility_id', '=', self.id)],
            'context': {'default_facility_id': self.id}
        }

    def action_open_settlement_wizard(self):
        """Open wizard to create settlement from dues"""
        self.ensure_one()

        return {
            'name': _('Create Settlement from Dues'),
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.settlement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_facility_id': self.id,
            }
        }
