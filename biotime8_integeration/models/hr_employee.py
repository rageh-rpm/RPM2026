# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json
import requests
import pytz
from datetime import datetime, timedelta
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class Employee(models.Model):
    _inherit = 'hr.employee'

    # Fields
    punch_from = fields.Date(string='Punch From Date')
    punch_to = fields.Date(string='Punch To Date')
    biotime_punches = fields.One2many('biotime.punch', inverse_name='employee_id', string='Biotime Punches')
    night_shift = fields.Boolean(string='Night Shift Employee')
    night_shift_ids = fields.One2many('hr.night.shift', 'employee_id', string='Night Shifts')
    late_checkins_ids = fields.One2many('hr.late.checkin', 'employee_id', string='Late Check-ins')
    late_hours_total = fields.Float(string='Total Late Hours', compute='_compute_late_hours_total', store=True)
    flexible_hours = fields.Boolean(string='Flexible Working Hours',
                                    help='Employee has flexible schedule without strict check-in times')

    @api.depends('late_checkins_ids.late_duration')
    def _compute_late_hours_total(self):
        """Compute total late hours from all late check-in records."""
        for employee in self:
            total_late_hours = sum(
                late_checkin.late_duration
                for late_checkin in employee.late_checkins_ids
            )
            employee.late_hours_total = total_late_hours

    def action_view_late_checkins(self):
        """Open late check-ins view for this employee."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Late Check-ins',
            'res_model': 'hr.late.checkin',
            'domain': [('employee_id', '=', self.id)],
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {'default_employee_id': self.id},
        }

    def create_in_biotime(self):
        """Create employee record in Biotime system."""
        for rec in self:
            try:
                auth_rec = self.env['biotime.connection'].search([('is_active', '=', True)], limit=1)
                if not auth_rec or not auth_rec.auth_code:
                    raise UserError('No active Biotime connection found. Please configure Biotime settings.')

                base_url = self._get_biotime_base_url()
                url = f"{base_url}/personnel/api/employee/?emp_code={rec.pin}"
                create_url = f"{base_url}/personnel/api/employees/"

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": auth_rec.auth_code,
                }

                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                resp_code = response.json()
                count = resp_code.get('count', 0)

                if count < 1:
                    _logger.info(f"Creating employee {rec.name} in Biotime")
                    data = {
                        "emp_code": rec.pin,
                        "first_name": rec.name,
                        "department": rec.department_id.biotime_department_id if rec.department_id else None,
                        "area": [2],
                    }
                    response = requests.post(create_url, data=json.dumps(data), headers=headers, timeout=10)
                    response.raise_for_status()
                    _logger.info(f"Employee created in Biotime: {response.text}")
                else:
                    _logger.info(f"Employee {rec.name} already exists in Biotime")

            except requests.exceptions.RequestException as e:
                raise UserError(f"Biotime API Error: {str(e)}")
            except Exception as e:
                _logger.error(f"Error creating employee in Biotime: {str(e)}")
                raise UserError(f"Failed to create employee in Biotime: {str(e)}")

    def action_all_month(self):
        """Create night shift records for remaining days in current month."""
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
            night_shift_vals = []
            for single_date in (start_date + timedelta(n) for n in range((end_date - start_date).days + 1)):
                if single_date > today:
                    night_shift_vals.append({
                        'employee_id': employee.id,
                        'date': single_date,
                    })

            if night_shift_vals:
                self.env['hr.night.shift'].create(night_shift_vals)

    def load_punches(self, punch_from, punch_to):

        for rec in self:
            # Step 1: Fetch the active Biotime connection record
            auth_rec = self.env['biotime.connection'].search([('is_active', '=', True)], limit=1)
            if not auth_rec or not auth_rec.auth_code:
                raise UserError(
                    "No active Biotime connection or missing authorization token. Please check Biotime settings.")  # [web:70]

            # ✅ Step 1.5: Delete existing attendance records in the date range
            try:
                # Support string or datetime inputs
                if isinstance(punch_from, str):
                    punch_from_dt = datetime.strptime(punch_from, '%Y-%m-%d %H:%M:%S')
                else:
                    punch_from_dt = punch_from

                if isinstance(punch_to, str):
                    punch_to_dt = datetime.strptime(punch_to, '%Y-%m-%d %H:%M:%S')
                else:
                    punch_to_dt = punch_to

                # Delete any attendance that lies fully inside the range
                existing_attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', rec.id),
                    '|',
                    '&', ('check_in', '>=', punch_from_dt), ('check_in', '<=', punch_to_dt),
                    '&', ('check_out', '>=', punch_from_dt), ('check_out', '<=', punch_to_dt),
                ])

                if existing_attendances:
                    existing_attendances.unlink()  # [web:70]

            except Exception as e:
                raise UserError(f"Error deleting existing attendance records: {str(e)}")

            # Step 2: Prepare URL and headers
            url = (
                f"http://172.20.10.11/iclock/api/transactions/"
                f"?emp_code={rec.pin}&page_size=100&start_time={punch_from}&end_time={punch_to}"
            )

            headers = {
                "Content-Type": "application/json",
                "Authorization": str(auth_rec.auth_code).strip(),
            }

            # Step 3: Perform API request safely
            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                raise UserError(f"Failed to fetch punches from Biotime: {str(e)}")

            # Step 4: Parse JSON safely
            try:
                list_url = response.json()
                punches = list_url.get("data", [])
            except Exception as e:
                raise UserError(f"Invalid response format from Biotime: {str(e)}")

            if not punches:
                continue  # no punches found for this employee

            # ✅ Step 5: Setup timezones - HARDCODED CAIRO
            api_timezone = pytz.timezone('Africa/Cairo')  # Biotime sends Cairo time [web:71]
            odoo_timezone = pytz.timezone('UTC')  # Odoo stores UTC

            # Step 6: Normalize punches
            punch_data = []
            for punch in punches:
                try:
                    punch_time = datetime.strptime(punch['punch_time'], '%Y-%m-%d %H:%M:%S')
                    punch_time = api_timezone.localize(punch_time).astimezone(odoo_timezone)
                    punch_time = punch_time.replace(tzinfo=None)
                    punch_data.append((punch_time, punch))
                except Exception:
                    continue  # skip invalid punch

            punch_data.sort()

            # Step 7: Gather employee data
            working_schedule = rec.resource_calendar_id.attendance_ids
            leave_type = self.env['hr.leave.type'].search([('weekend_replace', '=', True)], limit=1)
            if not leave_type:
                raise UserError("Leave type 'weekend_replace' not found.")  # [web:70]

            night_shifts = self.env['hr.night.shift'].search([('employee_id', '=', rec.id)])
            night_shift_dates = {shift.date for shift in night_shifts}

            # Step 8: Group punches by day
            punches_by_date = {}
            for punch_time, punch in punch_data:
                day = punch_time.date()
                punches_by_date.setdefault(day, []).append(punch_time)

            def is_scheduled_workday(calendar, day):
                weekday = day.weekday()
                return any(att.dayofweek == str(weekday) for att in calendar)

            # Step 9: Process punches by day
            for day, punches in sorted(punches_by_date.items()):
                punches.sort()
                is_night_shift_day = day in night_shift_dates
                is_working_day = is_scheduled_workday(working_schedule, day)
                next_day = day + timedelta(days=1)
                has_next_day_punches = next_day in punches_by_date
                next_day_punches = punches_by_date.get(next_day, [])

                if punches:

                    if len(punches) == 1:
                        single_punch_time = punches[0]
                        if is_night_shift_day:
                            day_start = datetime.combine(day, datetime.min.time())
                            day_end = datetime.combine(day, datetime.min.time()) + timedelta(days=1) - timedelta(
                                seconds=1)
                            if day_start <= single_punch_time <= day_end:
                                max_punch_time = max(punches)
                                if has_next_day_punches:
                                    min_punch_next_day = min(next_day_punches)
                                    if max_punch_time < min_punch_next_day:
                                        self.env['hr.attendance'].create({
                                            'employee_id': rec.id,
                                            'check_in': max_punch_time,
                                            'check_out': min_punch_next_day,
                                            'is_night_shift': True,
                                            'is_rest_day': not is_working_day,
                                        })
                                else:
                                    if max_punch_time < day_end:
                                        self.env['hr.attendance'].create({
                                            'employee_id': rec.id,
                                            'check_in': max_punch_time,
                                            'check_out': day_end,
                                            'is_night_shift': True,
                                            'is_rest_day': not is_working_day,
                                        })
                        else:
                            self.env['hr.attendance'].create({
                                'employee_id': rec.id,
                                'check_in': single_punch_time,
                                'check_out': single_punch_time,
                                'is_rest_day': not is_working_day,
                            })

                    elif len(punches) > 1:
                        first_punch_time = punches[0]
                        last_punch_time = punches[-1]
                        if is_night_shift_day:
                            if has_next_day_punches:
                                min_punch_next_day = min(next_day_punches)
                                self.env['hr.attendance'].create({
                                    'employee_id': rec.id,
                                    'check_in': max(punches),
                                    'check_out': min_punch_next_day,
                                    'is_night_shift': True,
                                    'is_rest_day': not is_working_day,
                                })
                            else:
                                day_end = datetime.combine(day, datetime.min.time()) + timedelta(days=1) - timedelta(
                                    seconds=1)
                                self.env['hr.attendance'].create({
                                    'employee_id': rec.id,
                                    'check_in': max(punches),
                                    'check_out': day_end,
                                    'is_night_shift': True,
                                    'is_rest_day': not is_working_day,
                                })
                        else:
                            self.env['hr.attendance'].create({
                                'employee_id': rec.id,
                                'check_in': first_punch_time,
                                'check_out': last_punch_time,
                                'is_rest_day': not is_working_day,
                            })

                    if not is_working_day and leave_type:
                        self.env['hr.leave.allocation'].create({
                            'employee_id': rec.id,
                            'holiday_status_id': leave_type.id,
                            'number_of_days': 1,
                            'name': f"Weekend Replace - {day}",
                        })

            # Step 10: Clean up invalid attendance records
            invalid_attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', rec.id),
                ('check_out', '!=', False),
                ('check_in', '!=', False),
            ]).filtered(lambda att: att.check_out < att.check_in)

            if invalid_attendances:
                invalid_attendances.unlink()

    def _process_daily_punches(self, punches, day, is_night_shift, is_working_day, next_day_punches):
        """
        Process punches for a single day and return attendance values.

        Returns:
            dict: Attendance values or None if no attendance should be created
        """
        self.ensure_one()

        if len(punches) == 1:
            return self._process_single_punch(
                punches[0], day, is_night_shift, is_working_day, next_day_punches
            )
        elif len(punches) > 1:
            return self._process_multiple_punches(
                punches, day, is_night_shift, is_working_day, next_day_punches
            )
        return None

    def _process_single_punch(self, punch_time, day, is_night_shift, is_working_day, next_day_punches):
        """Handle single punch scenario."""
        if is_night_shift:
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.min.time()) + timedelta(days=1) - timedelta(seconds=1)

            if day_start <= punch_time <= day_end:
                checkout = None
                if next_day_punches:
                    checkout = min(next_day_punches)
                else:
                    checkout = day_end

                return {
                    'employee_id': self.id,
                    'check_in': punch_time,
                    'check_out': checkout,
                    'is_night_shift': True,
                    'is_rest_day': not is_working_day
                }
        else:
            return {
                'employee_id': self.id,
                'check_in': punch_time,
                'check_out': punch_time,
                'is_rest_day': not is_working_day
            }
        return None

    def _process_multiple_punches(self, punches, day, is_night_shift, is_working_day, next_day_punches):
        """Handle multiple punches scenario."""
        first_punch = punches[0]
        last_punch = punches[-1]

        if is_night_shift:
            checkout = min(next_day_punches) if next_day_punches else \
                datetime.combine(day, datetime.min.time()) + timedelta(days=1) - timedelta(seconds=1)

            return {
                'employee_id': self.id,
                'check_in': last_punch,
                'check_out': checkout,
                'is_night_shift': True,
                'is_rest_day': not is_working_day
            }
        else:
            return {
                'employee_id': self.id,
                'check_in': first_punch,
                'check_out': last_punch,
                'is_rest_day': not is_working_day
            }

    def _is_scheduled_workday(self, calendar, day):
        """Check if a day is a scheduled working day according to employee's calendar."""
        weekday = str(day.weekday())
        return any(att.dayofweek == weekday for att in calendar)

    def _is_public_holiday(self, date):
        """Check if date is a public holiday for employee's location."""
        self.ensure_one()
        ResourceCalendarLeaves = self.env['resource.calendar.leaves']

        date_start = datetime.combine(date, datetime.min.time())
        date_end = datetime.combine(date, datetime.max.time())

        # Global company holidays
        leaves = ResourceCalendarLeaves.search([
            ('calendar_id', '=', self.resource_calendar_id.id),
            ('date_from', '<=', date_end),
            ('date_to', '>=', date_start),
            ('resource_id', '=', False),
        ])

        # Employee-specific leaves (approved time off)
        employee_leaves = ResourceCalendarLeaves.search([
            ('resource_id', '=', self.resource_id.id),
            ('date_from', '<=', date_end),
            ('date_to', '>=', date_start),
        ])

        return bool(leaves or employee_leaves)

    def _get_biotime_base_url(self):
        """Get Biotime base URL from configuration."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('biotime.base_url')
        if not base_url:
            base_url = 'http://172.20.10.11'  # Fallback to default
            _logger.warning('Biotime base URL not configured. Using default: %s', base_url)
        return base_url

    def _cleanup_invalid_attendances(self):
        """Remove invalid attendance records where check_out is before check_in."""
        # Use ORM instead of raw SQL for safety and proper field handling
        invalid_attendances = self.env['hr.attendance'].search([
            ('check_out', '!=', False),
            ('check_in', '!=', False),
        ])

        # Filter in Python to compare datetime fields properly
        to_delete = invalid_attendances.filtered(lambda att: att.check_out < att.check_in)

        if to_delete:
            _logger.warning(f"Removing {len(to_delete)} invalid attendance records where check_out < check_in")
            to_delete.unlink()

    def action_load_punches_wizard(self):
        """Open wizard to load punches for selected employees."""
        return {
            'name': 'Load Punches',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.punches.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_ids': self.ids},
        }

    def test_biotime_timezone(self):
        """Test to determine Biotime's timezone configuration."""
        self.ensure_one()

        auth_rec = self.env['biotime.connection'].search([('is_active', '=', True)], limit=1)
        if not auth_rec:
            raise UserError("No active Biotime connection found")

        # Get a recent punch from Biotime
        url = f"http://172.20.10.11/iclock/api/transactions/?emp_code={self.pin}&page_size=1"
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_rec.auth_code,
        }

        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        if not data.get('data'):
            raise UserError("No punch data found for this employee")

        # Get first punch
        punch = data['data'][0]
        biotime_time_str = punch['punch_time']

        # Parse it
        biotime_dt = datetime.strptime(biotime_time_str, '%Y-%m-%d %H:%M:%S')

        # Get current server time
        now_utc = datetime.utcnow()
        now_cairo = pytz.timezone('Africa/Cairo').localize(datetime.now()).replace(tzinfo=None)

        message = f"""
    BIOTIME TIMEZONE TEST
    =====================

    Sample Punch from Biotime:
      {biotime_time_str}

    Current Times:
      UTC:   {now_utc.strftime('%Y-%m-%d %H:%M:%S')}
      Cairo: {now_cairo.strftime('%Y-%m-%d %H:%M:%S')}

    Question: What time does the punch show in Biotime web interface?
    - If it matches UTC time above → Biotime uses UTC
    - If it matches Cairo time above → Biotime uses local Cairo time

    Check the Biotime web interface at:
    http://172.20.10.11

    Then compare the displayed punch time with the times above.
        """

        _logger.info(message)

        raise UserError(message)


    '''
    ============
    CRON METHODS 
    ===========
    '''


    @api.model
    def load_night_shift_punches(self):
        """Load punches only for employees with night shift scheduled yesterday."""
        env = self.env
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_date = yesterday.date()

        # Get employees who have night shift yesterday
        night_shift_emps = env['hr.night.shift'].search([('date', '=', yesterday_date)]).mapped('employee_id')
        if not night_shift_emps:
            return

        for emp in night_shift_emps:
            # Pull punches for yesterday until now (2 AM run time)
            punch_from = datetime.combine(yesterday_date, datetime.min.time())
            punch_to = datetime.now()
            emp.load_punches(punch_from, punch_to)

    @api.model
    def load_daily_punches(self):
        """Load punches for all employees for yesterday, used at 10 AM."""
        env = self.env
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_date = yesterday.date()

        all_emps = env['hr.employee'].search([('resource_calendar_id', '!=', False)])
        for emp in all_emps:
            punch_from = datetime.combine(yesterday_date, datetime.min.time())
            punch_to = datetime.now()
            emp.load_punches(punch_from, punch_to)
            print(punch_from,punch_to)


