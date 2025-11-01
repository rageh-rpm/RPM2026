from odoo import fields, models, api
from odoo.addons.base.models.res_partner import _tz_get

class ResCompany(models.Model):
    _inherit = 'res.company'

    day_shift_start = fields.Float("Day Shift Start Time")
    day_shift_end = fields.Float("Day Shift End Time")
    night_shift_start = fields.Float("Night Shift Start Time")
    night_shift_end = fields.Float("Night Shift End Time")
    day_ovt_end = fields.Float("DAy overtime End Time")
    timezone = fields.Selection(_tz_get, string='Timezone')
