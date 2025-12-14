# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrLateCheckin(models.Model):
    _name = 'hr.late.checkin'
    _description = 'Late Check-in Records'
    _order = 'date desc, employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                   ondelete='cascade', index=True)
    attendance_id = fields.Many2one('hr.attendance', string='Related Attendance',
                                     ondelete='cascade', index=True)
    date = fields.Date(string='Date', required=True, index=True)
    late_duration = fields.Float(string='Late Hours', digits=(16, 2), required=True)
    late_minutes = fields.Integer(string='Late Minutes', compute='_compute_late_minutes', store=True)
    scheduled_start = fields.Datetime(string='Scheduled Start Time')
    actual_start = fields.Datetime(string='Actual Check-in Time')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('deducted', 'Deducted from Payroll'),
        ('excused', 'Excused')
    ], default='draft', string='Status', required=True)
    notes = fields.Text(string='Notes')
    manager_notes = fields.Text(string='Manager Notes')

    @api.depends('late_duration')
    def _compute_late_minutes(self):
        """Convert late duration hours to minutes for better readability."""
        for record in self:
            record.late_minutes = int(record.late_duration * 60)

    @api.depends('employee_id', 'date')
    def name_get(self):
        """Display name format."""
        result = []
        for record in self:
            name = f"{record.employee_id.name} - {record.date} ({record.late_minutes} min)"
            result.append((record.id, name))
        return result

    _sql_constraints = [
        ('unique_late_checkin', 'unique(attendance_id)',
         'Late check-in record already exists for this attendance!')
    ]
