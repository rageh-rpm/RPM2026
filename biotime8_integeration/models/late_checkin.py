from odoo import fields, models, api


class LateCheckIn(models.Model):
    _name = 'hr.late.checkin'
    _description = 'Late Check-in Record'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    date = fields.Date(string="Date", required=True)
    late_duration = fields.Float(string="Late Duration (Hours)", required=True)
