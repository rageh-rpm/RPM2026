from odoo import models, fields, api

class EmployeePunchesWizard(models.TransientModel):
    _name = 'employee.punches.wizard'
    _description = 'Employee Punches Wizard'

    employee_ids = fields.Many2many('hr.employee', string="Employees")
    date_from = fields.Date(string="Date From", required=True)
    date_to = fields.Date(string="Date To", required=True)

    def action_confirm(self):
        for employee in self.employee_ids:
            employee.load_punches(self.date_from, self.date_to)
        return {'type': 'ir.actions.act_window_close'}
