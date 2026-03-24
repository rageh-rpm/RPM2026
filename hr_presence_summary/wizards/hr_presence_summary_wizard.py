# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class HrPresenceSummaryWizard(models.TransientModel):
    _name = 'hr.presence.summary.wizard'
    _description = 'Generate Presence Summaries'

    date_from = fields.Date(string='Date From', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Date To', required=True, default=fields.Date.context_today)
    employee_ids = fields.Many2many('hr.employee', string='Employees')

    def action_generate(self):
        self.ensure_one()
        summary_obj = self.env['hr.presence.summary']
        summary_obj.action_generate_summaries(
            self.date_from, 
            self.date_to, 
            self.employee_ids.ids if self.employee_ids else None
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Daily summaries have been generated.'),
                'sticky': False,
            }
        }
