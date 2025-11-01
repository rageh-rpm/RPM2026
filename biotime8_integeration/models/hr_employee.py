# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json
import requests
# from datetime import datetime
from datetime import datetime, timedelta
import pytz


class Employee(models.Model):
    _inherit = 'hr.employee'

    # biometric_id = fields.Char()
    punch_from = fields.Date()
    punch_to = fields.Date()
    biotime_punches = fields.One2many('biotime.punch',inverse_name='employee_id')
    night_shift = fields.Boolean()
    night_shift_ids = fields.One2many('hr.night.shift', 'employee_id', string='Night Shifts')
    late_checkins_ids = fields.One2many('hr.late.checkin', 'employee_id', string="Late Check-ins")
    late_hours_total = fields.Float(string='Total Late Hours', compute='_compute_late_hours_total')

    def _compute_late_hours_total(self):
        for employee in self:
            total_late_hours = sum(
                late_checkin.late_duration for late_checkin in self.env['hr.late.checkin'].search([('employee_id', '=', employee.id)])
            )
            employee.late_hours_total = total_late_hours

    def action_view_late_checkins(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Late Check-ins',
            'res_model': 'hr.late.checkin',
            'domain': [('employee_id', '=', self.id)],
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def create_in_biotime(self):
        for rec in self:
            auth_rec = self.env['biotime.connection'].search([('is_active', '=', True)], limit=1)
            url = "http://172.20.10.11/personnel/api/employee/?emp_code="+rec.pin
            create_url = "http://172.20.10.11/personnel/api/employees/"
            # use General token
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_rec.auth_code,
            }
            response = requests.get(url, headers=headers)
            print(response)
            resp_code = response.json()
            count = resp_code['count']
            if count < 1:
                print("Nopes!!")
                data = {
                    "emp_code": rec.pin,
                    "first_name": rec.name,
                    "department": rec.department_id.biotime_department_id,
                    "area": [2],
                }
                response = requests.post(create_url, data=json.dumps(data), headers=headers)
                print("Created",response.text)

    def action_all_month(self):
        today = datetime.now().date()
        start_date = today.replace(day=1)
        end_date = (today.replace(day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)

        for employee in self:
            # Remove existing night shift records for the current month
            self.env['hr.night.shift'].search([
                ('employee_id', '=', employee.id),
                ('date', '>=', start_date),
                ('date', '<=', end_date)
            ]).unlink()

            # Create records for each remaining day in the current month
            for single_date in (start_date + timedelta(n) for n in range((end_date - start_date).days + 1)):
                if single_date > today:
                    self.env['hr.night.shift'].create({
                        'employee_id': employee.id,
                        'date': single_date,
                    })

    def load_punches(self, punch_from, punch_to):
        for rec in self:
            # Fetch the authentication record
            auth_rec = self.env['biotime.connection'].search([('is_active', '=', True)], limit=1)
            url = f"http://172.20.10.11/iclock/api/transactions/?emp_code={rec.pin}&page_size=100&start_time={punch_from}&end_time={punch_to}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_rec.auth_code,
            }
            response = requests.get(url, headers=headers)
            list_url = response.json()
            punches = list_url["data"]

            # Define time zones
            api_timezone = self.env.company.timezone or 'UTC'
            api_timezone = pytz.timezone(api_timezone)  # API time zone
            odoo_timezone = pytz.timezone('UTC')  # Odoo server time zone, default to UTC

            # Convert punches to a list of tuples (datetime, punch)
            punch_data = []
            for punch in punches:
                punch_time = datetime.strptime(punch['punch_time'], '%Y-%m-%d %H:%M:%S')
                punch_time = api_timezone.localize(punch_time)  # Localize to API timezone
                punch_time = punch_time.astimezone(odoo_timezone)  # Convert to Odoo server timezone
                punch_time = punch_time.replace(tzinfo=None)  # Make datetime naive
                punch_data.append((punch_time, punch))

            punch_data.sort()

            # Get the employee's working schedule
            working_schedule = rec.resource_calendar_id.attendance_ids

            # Search for "weekend_replace" leave type
            leave_type = self.env['hr.leave.type'].search([('weekend_replace', '=', True)], limit=1)
            if not leave_type:
                raise ValueError("Leave type 'weekend_replace' not found.")

            # Get the list of night shift dates for the employee
            night_shifts = self.env['hr.night.shift'].search([('employee_id', '=', rec.id)])
            night_shift_dates = {shift.date for shift in night_shifts}

            # Create a dictionary to store punches by date
            punches_by_date = {}
            for punch_time, punch in punch_data:
                day = punch_time.date()
                if day not in punches_by_date:
                    punches_by_date[day] = []
                punches_by_date[day].append(punch_time)

            # Helper function to check if a day is a scheduled working day
            def is_scheduled_workday(calendar, day):
                weekday = day.weekday()
                return any(att.dayofweek == str(weekday) for att in calendar)

            # Process punches by day
            for day, punches in sorted(punches_by_date.items()):
                punches.sort()

                is_night_shift_day = day in night_shift_dates
                is_working_day = is_scheduled_workday(working_schedule, day)
                next_day = day + timedelta(days=1)
                has_next_day_punches = next_day in punches_by_date
                next_day_punches = punches_by_date.get(next_day, [])

                if is_working_day:
                    # Handle punches and create attendance as per existing logic
                    if len(punches) == 1:
                        single_punch_time = punches[0]

                        if is_night_shift_day:
                            # Night shift day handling (single punch)
                            day_start = datetime.combine(day, datetime.min.time())
                            day_end = datetime.combine(day, datetime.min.time()) + timedelta(days=1) - timedelta(
                                seconds=1)

                            if single_punch_time < day_start or single_punch_time > day_end:
                                continue

                            max_punch_time = max(punches)
                            if has_next_day_punches:
                                min_punch_next_day = min(next_day_punches)
                                if max_punch_time < min_punch_next_day:
                                    self.env['hr.attendance'].create({
                                        'employee_id': rec.id,
                                        'check_in': max_punch_time,
                                        'check_out': min_punch_next_day,
                                        'is_night_shift': is_night_shift_day
                                    })
                            else:
                                if max_punch_time < day_end:
                                    self.env['hr.attendance'].create({
                                        'employee_id': rec.id,
                                        'check_in': max_punch_time,
                                        'check_out': day_end,
                                        'is_night_shift': is_night_shift_day
                                    })
                        else:
                            # Handle single punch on a day shift day
                            self.env['hr.attendance'].create({
                                'employee_id': rec.id,
                                'check_in': single_punch_time,
                                'check_out': single_punch_time,
                            })

                    elif len(punches) > 1:
                        first_punch_time = punches[0]
                        last_punch_time = punches[-1]

                        if is_night_shift_day:
                            # Night shift handling (multiple punches)
                            if has_next_day_punches:
                                min_punch_next_day = min(next_day_punches)
                                self.env['hr.attendance'].create({
                                    'employee_id': rec.id,
                                    'check_in': max(punches),
                                    'check_out': min_punch_next_day,
                                    'is_night_shift': is_night_shift_day
                                })
                            else:
                                day_end = datetime.combine(day, datetime.min.time()) + timedelta(days=1) - timedelta(
                                    seconds=1)
                                self.env['hr.attendance'].create({
                                    'employee_id': rec.id,
                                    'check_in': max(punches),
                                    'check_out': day_end,
                                    'is_night_shift': is_night_shift_day
                                })
                        else:
                            # Day shift handling (multiple punches)
                            self.env['hr.attendance'].create({
                                'employee_id': rec.id,
                                'check_in': first_punch_time,
                                'check_out': last_punch_time,
                            })

                else:
                    # If punches occur outside of the working schedule, allocate "weekend_replace" leave
                    if len(punches) > 0:  # Ensure there is at least one punch
                        self.env['hr.leave.allocation'].create({
                            'employee_id': rec.id,
                            'holiday_status_id': leave_type.id,
                            'number_of_days': 1,
                            'name': f"Weekend Replace - {day}",
                        })

            # Additional validation to check for any erroneous records
            self.env.cr.execute("""
                DELETE FROM hr_attendance
                WHERE check_out < check_in
            """)

    def action_load_punches_wizard(self):
        return {
            'name': 'Load Punches',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.punches.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_ids': self.ids},
        }
