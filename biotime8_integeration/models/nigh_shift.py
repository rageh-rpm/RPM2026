from odoo import models, fields, api

class HRNightShift(models.Model):
    _name = 'hr.night.shift'
    _description = 'Night Shift'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    date = fields.Date(string='Date', required=True)
    notes = fields.Text(string='Notes')
