from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    day_shift_start = fields.Float("Day Shift Start Time", related='company_id.day_shift_start', readonly=False)
    day_shift_end = fields.Float("Day Shift End Time", related='company_id.day_shift_end', readonly=False)
    night_shift_start = fields.Float("Night Shift Start Time", related='company_id.night_shift_start', readonly=False)
    night_shift_end = fields.Float("Night Shift End Time", related='company_id.night_shift_end', readonly=False)
    day_ovt_end = fields.Float("Day OVT End", related='company_id.day_ovt_end', readonly=False)

    timezone = fields.Selection(related='company_id.timezone', string='Timezone', readonly=False)
