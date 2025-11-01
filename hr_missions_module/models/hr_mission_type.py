from odoo import fields, models, api

class HrMissionType(models.Model):
    _name = 'hr.mission.type'
    _description = 'Mission Type'

    name = fields.Char(required=True)
    apply_allowance = fields.Boolean(default=False)
    daily_allowance = fields.Float(string='Daily Allowance Amount', help="Daily allowance amount for this mission type")
    note = fields.Text()
    active = fields.Boolean(default=True)
    code = fields.Char(string='Code')
    max_duration = fields.Integer(string='Maximum Duration (Days)', help="Maximum allowed duration for this mission type")
    requires_approval = fields.Boolean(string='Requires Approval', default=True)
    currency_id = fields.Many2one("res.currency",string='Currency')
