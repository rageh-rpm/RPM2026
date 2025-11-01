from odoo import fields, models, api


class HrMissionTransportType(models.Model):
    _name = 'hr.mission.transport.type'
    _description = 'Mission Transport Type'

    name = fields.Char(required=True)
    apply_allowance = fields.Boolean(default=False)
    fixed_amount_in_country = fields.Float(string='In Country Amount Per KM')
    fixed_amount_abroad = fields.Float(string='Abroad Amount')
    personal_vehicle = fields.Boolean()
    note = fields.Text()
    active = fields.Boolean(default=True)
