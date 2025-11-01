from odoo import fields, models, api

class HrMissionAccommodationType(models.Model):
    _name = 'hr.mission.accommodation.type'
    _description = 'Mission Accommodation Type'

    name = fields.Char(required=True)
    apply_allowance = fields.Boolean(default=False)
    fixed_amount_in_country = fields.Float(string='In Country Amount')
    fixed_amount_abroad = fields.Float(string='Abroad Amount')
    note = fields.Text()
    active = fields.Boolean(default=True)
