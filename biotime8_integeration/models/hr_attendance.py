from odoo import fields, models, api
import datetime
import json
import requests
from datetime import datetime, timedelta
from odoo.osv.expression import AND, OR
import pytz
import logging

_logger = logging.getLogger(__name__)


class Attendance(models.Model):
    _inherit = 'hr.attendance'

    is_night_shift = fields.Boolean()



    def create_in_biotime(self):
        for rec in self:
            auth_rec = self.env['biotime.connection'].search([('is_active', '=', True)], limit=1)
            url = "http://172.20.10.11/personnel/api/departments/?dept_code="+rec.biotime_department_id
            create_url = "http://172.20.10.11/personnel/api/departments/"
            # use General token
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_rec.auth_code,
            }
            response = requests.get(url, headers=headers)
            # print(response.text)
            resp_code = response.json()
            count = resp_code['count']
            if count < 1:
                print("Nopes!!")
                data = {
                    "dept_code": rec.biotime_department_id,
                    "dept_name": rec.name,
                }
                response = requests.post(create_url, data=json.dumps(data), headers=headers)
                print("Created",response.text)



        return datetime.datetime.combine(self.invoice_date, datetime.datetime.min.time())


    def _update_overtime(self, employee_attendance_dates=None):
        if employee_attendance_dates is None:
            # TODO Overtime Approval Cycle
            employee_attendance_dates = self._get_attendances_dates()

        overtime_vals_list = []

        for emp, attendance_dates in employee_attendance_dates.items():
            company = self.env.company
            day_shift_start = company.day_shift_start
            day_shift_end = company.day_shift_end
            night_shift_start = company.night_shift_start
            night_shift_end = company.night_shift_end
            company_timezone = pytz.timezone(company.timezone)

            attendance_domain = []
            for attendance_date in attendance_dates:
                attendance_domain.append([
                    ('check_in', '>=', attendance_date[0]),
                    ('check_in', '<', attendance_date[0] + timedelta(hours=24)),
                ])
            attendance_domain = [('employee_id', '=', emp.id)] + OR(attendance_domain)

            attendances = self.env['hr.attendance'].search(attendance_domain)

            for attendance in attendances:
                if not attendance.check_in or not attendance.check_out:
                    continue  # Skip if check_in or check_out is not set

                punch_in_time = attendance.check_in
                punch_out_time = attendance.check_out
                utc_punch_in_time = pytz.utc.localize(punch_in_time)
                utc_punch_out_time = pytz.utc.localize(punch_out_time)
                local_punch_in_time = utc_punch_in_time.astimezone(company_timezone)
                local_punch_out_time = utc_punch_out_time.astimezone(company_timezone)

                # Determine the planned start time based on the shift type
                planned_start_time = None
                if attendance.is_night_shift:
                    # For night shift, compare with the start time
                    planned_start_time = local_punch_in_time.replace(hour=int(night_shift_start), minute=0)
                else:
                    # For day shift, compare with the start time
                    planned_start_time = local_punch_in_time.replace(hour=int(day_shift_start), minute=0)

                # Calculate late check-in duration
                late_duration_minutes = 0
                if local_punch_in_time > planned_start_time:
                    late_duration_minutes = (local_punch_in_time - planned_start_time).seconds // 60

                if late_duration_minutes > 0:
                    date = local_punch_in_time.date()
                    hours = late_duration_minutes // 60
                    minutes = late_duration_minutes % 60

                    # Store late check-in
                    self.env['hr.late.checkin'].create({
                        'employee_id': emp.id,
                        'date': date,
                        'late_duration': hours + (minutes / 60),
                    })

                # Calculate overtime
                overtime_minutes = 0

                if attendance.is_night_shift:
                    planned_end_time = local_punch_out_time.replace(hour=int(night_shift_end), minute=0)
                    if local_punch_out_time > planned_end_time:
                        overtime_minutes = (local_punch_out_time - planned_end_time).seconds // 60
                else:
                    planned_end_time = local_punch_out_time.replace(hour=int(day_shift_end), minute=0)
                    if local_punch_out_time > planned_end_time:
                        overtime_minutes = (local_punch_out_time - planned_end_time).seconds // 60

                if overtime_minutes > 0:
                    date = local_punch_out_time.date()
                    hours = overtime_minutes // 60
                    minutes = overtime_minutes % 60

                    # Store overtime
                    existing_overtime = self.env['hr.attendance.overtime'].search([
                        ('employee_id', '=', emp.id),
                        ('date', '=', date)
                    ], limit=1)
                    existing_overtime.unlink()

                    # if existing_overtime:
                    #     existing_overtime.write({
                    #         'duration': existing_overtime.duration + hours,
                    #         'duration_real': existing_overtime.duration_real + hours,
                    #     })

                    overtime_vals_list.append({
                            'employee_id': emp.id,
                            'date': date,
                            'duration': hours + (minutes / 60),  # Store duration as a float if needed
                            'duration_real': hours + (minutes / 60),  # Store duration as a float if needed
                        })

        # Create or update overtime records
        if overtime_vals_list:
            self.env['hr.attendance.overtime'].sudo().create(overtime_vals_list)


    @api.depends('check_in', 'check_out')
    def _compute_overtime_hours(self):
        """Link attendance to overtime duration — no recalculation."""
        Overtime = self.env['hr.attendance.overtime']
        for att in self:
            duration = 0.0
            if att.employee_id and att.check_out:
                overtime = Overtime.search([
                    ('employee_id', '=', att.employee_id.id),
                    ('date', '=', att.check_out.date())
                ], limit=1)
                duration = overtime.duration_real if overtime else 0.0
            att.overtime_hours = duration


class BiotimePunch(models.Model):
    _name = "biotime.punch"
    _description = 'BioTime raw punch'

    name = fields.Integer()
    emp_code = fields.Char()
    first_name = fields.Char()
    last_name = fields.Char()
    department = fields.Char()
    punch_time = fields.Datetime()
    punch_state_display = fields.Char()
    verify_type_display = fields.Char()
    terminal_alias = fields.Char()
    employee_id = fields.Many2one('hr.employee')
