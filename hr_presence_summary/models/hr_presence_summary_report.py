from odoo import models, api, _
from datetime import timedelta

class HrPresenceMatrixReport(models.AbstractModel):
    _name = 'report.hr_presence_summary.report_presence_matrix_template'
    _description = 'Presence Matrix Report Logic'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.presence.summary'].browse(docids)
        
        # Determine the full date range from selected records
        raw_dates = docs.mapped('date')
        if not raw_dates:
            return {'doc_ids': docids, 'doc_model': 'hr.presence.summary', 'docs': docs}
            
        start_date = min(raw_dates)
        end_date = max(raw_dates)
        
        dates = []
        curr = start_date
        while curr <= end_date:
            dates.append(curr)
            curr += timedelta(days=1)
            
        employees = docs.mapped('employee_id').sorted(key=lambda e: (e.department_id.name or '', e.name))
        
        matrix_data = []
        for emp in employees:
            emp_date_status = {}
            emp_docs = docs.filtered(lambda x: x.employee_id == emp)
            for d in dates:
                day_docs = emp_docs.filtered(lambda x: x.date == d)
                if day_docs:
                    # If multiple, take the first one or combine?
                    # The user wants "presence type", so we use the shorthand
                    emp_date_status[d] = ", ".join([doc.shorthand_status for doc in day_docs])
                else:
                    emp_date_status[d] = ""
            
            matrix_data.append({
                'employee': emp,
                'status_by_date': emp_date_status
            })

        return {
            'doc_ids': docids,
            'doc_model': 'hr.presence.summary',
            'docs': docs,
            'dates': dates,
            'matrix_data': matrix_data,
        }
