from odoo import fields, models, api


class HrMissionAllowance(models.Model):
    _name = 'hr.mission.allowance'
    _description = 'Mission Allowance Line'

    mission_id = fields.Many2one('hr.mission', string='Mission', required=True, ondelete='cascade')
    name = fields.Char(string='Description', required=True)
    allowance_type = fields.Selection([
        ('accommodation', 'Accommodation'),
        ('transportation', 'Transportation'),
        ('fixed_fare', 'Fixed Fare'),
        ('daily', 'Daily Allowance'),
        ('other', 'Other')
    ], string='Type', required=True)
    amount = fields.Float(string='Unit Amount', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)

    @api.depends('amount', 'quantity')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.amount * record.quantity