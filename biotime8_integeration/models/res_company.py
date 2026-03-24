# -*- coding: utf-8 -*-

from odoo import models, fields
from odoo.addons.base.models.res_partner import _tz_get



class ResCompany(models.Model):
    _inherit = 'res.company'

    # Shift timing configuration
    day_shift_start = fields.Float(
        string='Day Shift Start',
        default=8.0,
        help='Start time for day shift (24-hour format, e.g., 8.0 for 8:00 AM)'
    )
    day_shift_end = fields.Float(
        string='Day Shift End',
        default=17.0,
        help='End time for day shift (24-hour format, e.g., 17.0 for 5:00 PM)'
    )
    day_ovt_end = fields.Float(
        string='Day Overtime End',
        default=21.0,
        help='Maximum end time for day shift overtime (e.g., 21.0 for 9:00 PM)'
    )
    night_shift_start = fields.Float(
        string='Night Shift Start',
        default=22.0,
        help='Start time for night shift (24-hour format, e.g., 22.0 for 10:00 PM)'
    )
    night_shift_end = fields.Float(
        string='Night Shift End',
        default=6.0,
        help='End time for night shift (24-hour format, e.g., 6.0 for 6:00 AM)'
    )

    # Tolerance configuration
    late_checkin_tolerance = fields.Integer(
        string='Late Check-in Tolerance (minutes)',
        default=5,
        help='Grace period in minutes before marking as late'
    )
    overtime_tolerance_company = fields.Integer(
        string='Overtime Tolerance (minutes)',
        default=15,
        help='Minimum minutes after schedule end to count as overtime'
    )

    # Timezone Configuration
    timezone = fields.Selection(_tz_get, string='Timezone')


