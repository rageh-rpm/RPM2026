# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class OverdraftRateChangeWizard(models.TransientModel):
    _name = 'overdraft.rate.change.wizard'
    _description = 'Change Overdraft Interest Rate'

    facility_id = fields.Many2one('overdraft.facility', string='Facility', required=True, readonly=True)
    facility_name = fields.Char(related='facility_id.name', string='Facility Reference')
    current_rate = fields.Float(string='Current Rate (%)', readonly=True, digits=(5, 2))
    new_rate = fields.Float(string='New Rate (%)', required=True, digits=(5, 2))
    effective_date = fields.Date(
        string='Effective From',
        required=True,
        default=fields.Date.today,
        help='Date from which the new rate becomes effective'
    )
    reason = fields.Text(string='Reason for Change', help='Explain why the rate is being changed')

    affected_payments_count = fields.Integer(
        string='Affected Payments',
        compute='_compute_affected_payments'
    )

    @api.depends('facility_id', 'effective_date')
    def _compute_affected_payments(self):
        for wizard in self:
            if wizard.facility_id and wizard.effective_date:
                # Count payments with interest start date before effective date and settlement due after
                affected = self.env['account.payment'].search_count([
                    ('overdraft_facility_id', '=', wizard.facility_id.id),
                    ('interest_start_date', '<=', wizard.effective_date),
                    ('settlement_due_date', '>=', wizard.effective_date),
                    ('settlement_status', 'in', ['pending', 'partial'])
                ])
                wizard.affected_payments_count = affected
            else:
                wizard.affected_payments_count = 0

    @api.constrains('new_rate')
    def _check_new_rate(self):
        for wizard in self:
            if wizard.new_rate < 0 or wizard.new_rate > 100:
                raise ValidationError(_('Interest rate must be between 0 and 100!'))

    @api.constrains('effective_date', 'facility_id')
    def _check_effective_date(self):
        for wizard in self:
            if wizard.facility_id and wizard.effective_date:
                if not (wizard.facility_id.date_from <= wizard.effective_date <= wizard.facility_id.date_to):
                    raise ValidationError(_(
                        'Effective date must be within facility period!\n'
                        'Facility Period: %s to %s'
                    ) % (wizard.facility_id.date_from, wizard.facility_id.date_to))

    def action_apply_rate_change(self):
        self.ensure_one()

        if abs(self.new_rate - self.current_rate) < 0.01:
            raise ValidationError(_('New rate must be different from current rate!'))

        # Create rate history record
        self.env['overdraft.interest.rate.history'].create({
            'facility_id': self.facility_id.id,
            'effective_date': self.effective_date,
            'annual_interest_rate': self.new_rate,
            'previous_rate': self.current_rate,
            'reason': self.reason,
        })

        # Post message to facility
        self.facility_id.message_post(
            body=_(
                'Interest rate changed from %(old)s%% to %(new)s%% effective %(date)s.<br/>Reason: %(reason)s<br/>Affected payments: %(count)s') % {
                     'old': self.current_rate,
                     'new': self.new_rate,
                     'date': self.effective_date,
                     'reason': self.reason or 'Not specified',
                     'count': self.affected_payments_count
                 }
        )

        # Show success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _(
                    'Interest rate changed successfully. %s payment(s) will be affected.') % self.affected_payments_count,
                'type': 'success',
                'sticky': False,
            }
        }
