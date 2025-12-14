# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Shift Timing Configuration
    day_shift_start = fields.Float(
        string="Day Shift Start Time",
        related='company_id.day_shift_start',
        readonly=False,
        help="Start time for day shift in 24-hour format (e.g., 8.0 for 8:00 AM, 8.5 for 8:30 AM)"
    )
    day_shift_end = fields.Float(
        string="Day Shift End Time",
        related='company_id.day_shift_end',
        readonly=False,
        help="End time for day shift in 24-hour format (e.g., 17.0 for 5:00 PM)"
    )
    night_shift_start = fields.Float(
        string="Night Shift Start Time",
        related='company_id.night_shift_start',
        readonly=False,
        help="Start time for night shift in 24-hour format (e.g., 22.0 for 10:00 PM)"
    )
    night_shift_end = fields.Float(
        string="Night Shift End Time",
        related='company_id.night_shift_end',
        readonly=False,
        help="End time for night shift in 24-hour format (e.g., 6.0 for 6:00 AM next day)"
    )
    day_ovt_end = fields.Float(
        string="Day Overtime End Time",
        related='company_id.day_ovt_end',
        readonly=False,
        help="Maximum end time for day shift overtime calculation (e.g., 21.0 for 9:00 PM)"
    )

    # Tolerance Configuration
    late_checkin_tolerance = fields.Integer(
        string='Late Check-in Tolerance (minutes)',
        related='company_id.late_checkin_tolerance',
        readonly=False,
        help='Grace period in minutes before marking employee as late (e.g., 5 minutes)'
    )
    overtime_tolerance_company = fields.Integer(
        string='Overtime Tolerance (minutes)',
        related='company_id.overtime_tolerance_company',
        readonly=False,
        help='Minimum minutes beyond schedule to count as overtime (e.g., 15 minutes)'
    )

    # Timezone Configuration
    timezone = fields.Selection(
        related='company_id.timezone',
        string='Company Timezone',
        required=True,
        readonly=False,
        help='Timezone used for attendance and shift calculations'
    )

    # Biotime Integration Settings
    biotime_base_url = fields.Char(
        string='Biotime Server URL',
        config_parameter='biotime.base_url',
        help='Base URL for Biotime API (e.g., http://172.20.10.11)'
    )
    biotime_api_timeout = fields.Integer(
        string='Biotime API Timeout (seconds)',
        config_parameter='biotime.api_timeout',
        default=15,
        help='Request timeout for Biotime API calls'
    )

    @api.constrains('day_shift_start', 'day_shift_end')
    def _check_day_shift_times(self):
        """Validate day shift times are logical."""
        for record in self:
            if record.day_shift_start >= record.day_shift_end:
                raise models.ValidationError(
                    'Day shift start time must be before end time.'
                )
            if record.day_shift_start < 0 or record.day_shift_start >= 24:
                raise models.ValidationError(
                    'Day shift start time must be between 0 and 24 hours.'
                )
            if record.day_shift_end < 0 or record.day_shift_end >= 24:
                raise models.ValidationError(
                    'Day shift end time must be between 0 and 24 hours.'
                )

    @api.constrains('night_shift_start', 'night_shift_end')
    def _check_night_shift_times(self):
        """Validate night shift times."""
        for record in self:
            if record.night_shift_start < 0 or record.night_shift_start >= 24:
                raise models.ValidationError(
                    'Night shift start time must be between 0 and 24 hours.'
                )
            if record.night_shift_end < 0 or record.night_shift_end >= 24:
                raise models.ValidationError(
                    'Night shift end time must be between 0 and 24 hours.'
                )

    @api.constrains('day_ovt_end')
    def _check_day_ovt_end(self):
        """Validate day overtime end time."""
        for record in self:
            if record.day_ovt_end and (record.day_ovt_end < 0 or record.day_ovt_end >= 24):
                raise models.ValidationError(
                    'Day overtime end time must be between 0 and 24 hours.'
                )
            if record.day_ovt_end and record.day_shift_end and record.day_ovt_end <= record.day_shift_end:
                raise models.ValidationError(
                    'Day overtime end time must be after day shift end time.'
                )

    @api.constrains('late_checkin_tolerance', 'overtime_tolerance_company')
    def _check_tolerance_values(self):
        """Validate tolerance values are reasonable."""
        for record in self:
            if record.late_checkin_tolerance < 0 or record.late_checkin_tolerance > 60:
                raise models.ValidationError(
                    'Late check-in tolerance must be between 0 and 60 minutes.'
                )
            if record.overtime_tolerance_company < 0 or record.overtime_tolerance_company > 60:
                raise models.ValidationError(
                    'Overtime tolerance must be between 0 and 60 minutes.'
                )

    @api.onchange('day_shift_start', 'day_shift_end')
    def _onchange_day_shift_times(self):
        """Provide helpful warning if shift duration seems unusual."""
        if self.day_shift_start and self.day_shift_end:
            duration = self.day_shift_end - self.day_shift_start
            if duration < 4:
                return {
                    'warning': {
                        'title': 'Short Shift Duration',
                        'message': 'Day shift duration is less than 4 hours. Please verify the times are correct.'
                    }
                }
            elif duration > 12:
                return {
                    'warning': {
                        'title': 'Long Shift Duration',
                        'message': 'Day shift duration exceeds 12 hours. Please verify the times are correct.'
                    }
                }
