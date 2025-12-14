# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class OverdraftInterestRateHistory(models.Model):
    _name = 'overdraft.interest.rate.history'
    _description = 'Overdraft Interest Rate Change History'
    _order = 'effective_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True
    )

    facility_id = fields.Many2one(
        'overdraft.facility',
        string='Facility',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    effective_date = fields.Date(
        string='Effective Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date from which this rate becomes effective'
    )

    annual_interest_rate = fields.Float(
        string='Annual Interest Rate (%)',
        required=True,
        digits=(5, 2),
        tracking=True,
        help='New annual interest rate'
    )

    daily_interest_rate = fields.Float(
        string='Daily Interest Rate (%)',
        compute='_compute_daily_rate',
        store=True,
        digits=(8, 6),
        help='Daily rate = Annual Rate / 365'
    )

    reason = fields.Text(
        string='Change Reason',
        tracking=True,
        help='Reason for rate change (e.g., Bank policy change)'
    )

    previous_rate = fields.Float(
        string='Previous Rate (%)',
        digits=(5, 2),
        readonly=True
    )

    auto_recalculate = fields.Boolean(
        string='Auto-Recalculate Interest',
        default=True,
        help='Automatically recalculate pending interest accruals when this rate change is saved'
    )

    recalculated_payment_count = fields.Integer(
        string='Recalculated Payments',
        readonly=True,
        help='Number of payments that had their interest recalculated'
    )

    company_id = fields.Many2one('res.company', related='facility_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='facility_id.currency_id')

    @api.depends('facility_id.name', 'effective_date', 'annual_interest_rate')
    def _compute_name(self):
        for record in self:
            if record.facility_id and record.effective_date:
                record.name = f"{record.facility_id.name} - {record.annual_interest_rate}% from {record.effective_date}"
            else:
                record.name = _('New Rate Change')

    @api.depends('annual_interest_rate')
    def _compute_daily_rate(self):
        for record in self:
            record.daily_interest_rate = record.annual_interest_rate / 365 if record.annual_interest_rate else 0.0

    @api.constrains('annual_interest_rate')
    def _check_rate(self):
        for record in self:
            if record.annual_interest_rate < 0 or record.annual_interest_rate > 100:
                raise ValidationError(_('Interest rate must be between 0 and 100!'))

    @api.constrains('facility_id', 'effective_date')
    def _check_duplicate_date(self):
        for record in self:
            duplicate = self.search([
                ('id', '!=', record.id),
                ('facility_id', '=', record.facility_id.id),
                ('effective_date', '=', record.effective_date)
            ])
            if duplicate:
                raise ValidationError(_('A rate change already exists for this date!'))

    @api.constrains('effective_date', 'facility_id')
    def _check_date_in_facility_period(self):
        for record in self:
            if record.facility_id and record.effective_date:
                if not (record.facility_id.date_from <= record.effective_date <= record.facility_id.date_to):
                    raise ValidationError(_(
                        'Effective date must be within facility period!\n'
                        'Facility Period: %s to %s\n'
                        'Effective Date: %s'
                    ) % (
                                              record.facility_id.date_from,
                                              record.facility_id.date_to,
                                              record.effective_date
                                          ))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # Auto-recalculate interest for affected payments
        for record in records:
            if record.auto_recalculate:
                record._recalculate_affected_payments()

        return records

    def _recalculate_affected_payments(self):
        """Recalculate interest for payments affected by this rate change"""
        self.ensure_one()

        # Find payments where interest period includes this effective date
        # AND payment is not yet fully settled
        affected_payments = self.env['account.payment'].search([
            ('overdraft_facility_id', '=', self.facility_id.id),
            ('interest_start_date', '<=', self.effective_date),
            ('settlement_due_date', '>=', self.effective_date),
            ('settlement_status', 'in', ['pending', 'partial']),
            ('state', 'in', ['posted', 'paid'])
        ])

        recalculated_count = 0

        for payment in affected_payments:
            # Delete only DRAFT accruals (don't touch posted ones)
            draft_accruals = payment.interest_accrual_ids.filtered(lambda a: a.state == 'draft')

            if draft_accruals:
                draft_accruals.unlink()

                # Recreate with new rate calculation
                new_accrual = payment._create_interest_accrual()

                if new_accrual:
                    recalculated_count += 1

                    payment.message_post(
                        body=_('Interest recalculated due to rate change to %s%% effective %s') % (
                            self.annual_interest_rate,
                            self.effective_date
                        )
                    )

        # Update counter
        self.recalculated_payment_count = recalculated_count

        # Post message
        if recalculated_count > 0:
            self.message_post(
                body=_('Interest automatically recalculated for %s payment(s)') % recalculated_count
            )

            self.facility_id.message_post(
                body=_('Rate changed to %s%% effective %s. Interest recalculated for %s payment(s).') % (
                    self.annual_interest_rate,
                    self.effective_date,
                    recalculated_count
                )
            )

