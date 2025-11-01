from odoo import fields, models, api


class LeaveType(models.Model):
    _inherit = 'hr.leave.type'

    weekend_replace = fields.Boolean()