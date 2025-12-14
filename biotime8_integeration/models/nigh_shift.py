# -*- coding: utf-8 -*-

from odoo import models, fields


class HrNightShift(models.Model):
    _name = 'hr.night.shift'
    _description = 'Night Shift Schedule'
    _order = 'date desc, employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                   ondelete='cascade', index=True)
    date = fields.Date(string='Night Shift Date', required=True, index=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_night_shift', 'unique(employee_id, date)',
         'Night shift already scheduled for this employee on this date!')
    ]

    def name_get(self):
        """Display name format."""
        result = []
        for record in self:
            name = f"{record.employee_id.name} - {record.date}"
            result.append((record.id, name))
        return result
