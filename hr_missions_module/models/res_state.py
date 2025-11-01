from odoo import fields, models, api


class State(models.Model):
    _inherit = 'res.country.state'

    distance_km = fields.Float()
    fixed_fare = fields.Float()