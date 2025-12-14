# -*- coding: utf-8 -*-

from odoo import fields, models, api
from datetime import datetime, timedelta
from odoo.osv.expression import OR
import pytz
import logging

_logger = logging.getLogger(__name__)


class Attendance(models.Model):
    _inherit = 'hr.attendance'

    is_night_shift = fields.Boolean(string='Night Shift', default=False)
    is_rest_day = fields.Boolean(string='Rest Day', default=False,
                                 help='Attendance on non-working day (weekend/holiday)')

    @api.depends('check_in', 'check_out')
    def _compute_overtime_hours(self):
        """
        Link attendance to overtime duration - lookup only, no recalculation.
        Actual calculation happens in _update_overtime().
        """
        Overtime = self.env['hr.attendance.overtime']
        company_tz = pytz.timezone(self.env.company.timezone or 'UTC')

        for att in self:
            duration = 0.0
            if att.employee_id and att.check_out:
                try:
                    # Convert UTC datetime to company's local timezone
                    local_check_out = pytz.utc.localize(att.check_out).astimezone(company_tz)
                    local_date = local_check_out.date()

                    overtime = Overtime.search([
                        ('employee_id', '=', att.employee_id.id),
                        ('date', '=', local_date)
                    ], limit=1)

                    duration = overtime.duration_real if overtime else 0.0
                except Exception as e:
                    _logger.error(f"Error computing overtime hours for attendance {att.id}: {str(e)}")

            att.overtime_hours = duration

    # def _update_overtime(self, employee_attendance_dates=None):
    #     """
    #     Calculate and update overtime and late check-in records based on employee schedules.
    #     This method processes attendance records and creates/updates overtime and late check-in records.
    #     """
    #     if employee_attendance_dates is None:
    #         employee_attendance_dates = self._get_attendances_dates()
    #
    #     overtime_vals_list = []
    #     late_checkin_vals_list = []
    #
    #     for emp, attendance_dates in employee_attendance_dates.items():
    #         company = self.env.company
    #         company_timezone = pytz.timezone(company.timezone or 'UTC')
    #
    #         # Get tolerance settings
    #         late_tolerance = company.late_checkin_tolerance or 5
    #         overtime_tolerance = company.overtime_tolerance_company or 15
    #
    #         # Build attendance domain
    #         attendance_domain = []
    #         for attendance_date in attendance_dates:
    #             attendance_domain.append([
    #                 ('check_in', '>=', attendance_date[0]),
    #                 ('check_in', '<', attendance_date[0] + timedelta(hours=24)),
    #             ])
    #         attendance_domain = [('employee_id', '=', emp.id)] + OR(attendance_domain)
    #
    #         attendances = self.env['hr.attendance'].search(attendance_domain)
    #
    #         for attendance in attendances:
    #             if not attendance.check_in or not attendance.check_out:
    #                 continue
    #
    #             try:
    #                 # Convert to local timezone
    #                 utc_punch_in = pytz.utc.localize(attendance.check_in)
    #                 utc_punch_out = pytz.utc.localize(attendance.check_out)
    #                 local_punch_in = utc_punch_in.astimezone(company_timezone)
    #                 local_punch_out = utc_punch_out.astimezone(company_timezone)
    #                 check_in_date = local_punch_in.date()
    #                 check_out_date = local_punch_out.date()
    #
    #                 # Get scheduled times based on shift type
    #                 if attendance.is_night_shift:
    #                     planned_start, planned_end = self._get_night_shift_schedule(
    #                         company, local_punch_in, local_punch_out
    #                     )
    #                 else:
    #                     # Get employee's actual schedule for the day
    #                     planned_start, planned_end = self._get_employee_schedule_for_date(
    #                         emp, check_in_date
    #                     )
    #
    #                     if not planned_start:
    #                         # No schedule = rest day or flexible hours
    #                         _logger.debug(f"No schedule found for {emp.name} on {check_in_date}")
    #                         continue
    #
    #                 # Calculate and store late check-in
    #                 late_vals = self._calculate_late_checkin(
    #                     emp, attendance, local_punch_in, planned_start,
    #                     check_in_date, late_tolerance
    #                 )
    #                 if late_vals:
    #                     late_checkin_vals_list.append(late_vals)
    #
    #                 # Calculate and store overtime
    #                 overtime_vals = self._calculate_overtime(
    #                     emp, local_punch_out, planned_end,
    #                     check_out_date, overtime_tolerance
    #                 )
    #                 if overtime_vals:
    #                     overtime_vals_list.append(overtime_vals)
    #
    #             except Exception as e:
    #                 _logger.error(f"Error processing attendance {attendance.id}: {str(e)}")
    #                 continue
    #
    #     # Batch create records
    #     if late_checkin_vals_list:
    #         # Remove existing late check-ins for these dates to avoid duplicates
    #         self._cleanup_existing_late_checkins(late_checkin_vals_list)
    #         self.env['hr.late.checkin'].create(late_checkin_vals_list)
    #         _logger.info(f"Created {len(late_checkin_vals_list)} late check-in records")
    #
    #     if overtime_vals_list:
    #         # Update or create overtime records
    #         self._create_or_update_overtime(overtime_vals_list)
    #         _logger.info(f"Processed {len(overtime_vals_list)} overtime records")

    def _update_overtime(self, employee_attendance_dates=None):
        """
        Calculate and update overtime and late check-in records based on employee schedules.
        Night shift overtime will take first check-in and last check-out.
        """
        if employee_attendance_dates is None:
            employee_attendance_dates = self._get_attendances_dates()

        overtime_vals_list = []
        late_checkin_vals_list = []

        for emp, attendance_dates in employee_attendance_dates.items():
            company = self.env.company
            company_timezone = pytz.timezone(company.timezone or 'UTC')

            # Get tolerance settings
            late_tolerance = company.late_checkin_tolerance or 5
            overtime_tolerance = company.overtime_tolerance_company or 15

            for attendance_date in attendance_dates:

                # 🔹 جمع كل الحضور لنفس اليوم أو الليلي
                attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', emp.id),
                    ('check_in', '>=', attendance_date[0]),
                    ('check_in', '<', attendance_date[0] + timedelta(hours=36)),
                    ('check_out', '!=', False),
                ], order='check_in asc')

                if not attendances:
                    continue

                # 🔹 لو الشيفت ليلي خد أول دخول وآخر خروج
                night_shift_att = attendances.filtered(lambda a: a.is_night_shift)
                if night_shift_att:
                    first_att = night_shift_att[0]
                    last_att = night_shift_att[-1]

                    utc_punch_in = pytz.utc.localize(first_att.check_in)
                    utc_punch_out = pytz.utc.localize(last_att.check_out)
                    local_punch_in = utc_punch_in.astimezone(company_timezone)
                    local_punch_out = utc_punch_out.astimezone(company_timezone)

                    planned_start, planned_end = self._get_night_shift_schedule(
                        company, local_punch_in, local_punch_out
                    )

                    # حساب Late Check-in لأول حضور فقط
                    late_vals = self._calculate_late_checkin(
                        emp, first_att, local_punch_in, planned_start,
                        local_punch_in.date(), late_tolerance
                    )
                    if late_vals:
                        late_checkin_vals_list.append(late_vals)

                    # حساب Overtime على آخر خروج
                    overtime_vals = self._calculate_overtime(
                        emp, local_punch_out, planned_end,
                        local_punch_out.date(), overtime_tolerance
                    )
                    if overtime_vals:
                        overtime_vals_list.append(overtime_vals)

                else:
                    # باقي الشيفتات العادية تفضل على كل حضور
                    for attendance in attendances:
                        if not attendance.check_in or not attendance.check_out:
                            continue

                        try:
                            utc_punch_in = pytz.utc.localize(attendance.check_in)
                            utc_punch_out = pytz.utc.localize(attendance.check_out)
                            local_punch_in = utc_punch_in.astimezone(company_timezone)
                            local_punch_out = utc_punch_out.astimezone(company_timezone)
                            check_in_date = local_punch_in.date()
                            check_out_date = local_punch_out.date()

                            planned_start, planned_end = self._get_employee_schedule_for_date(
                                emp, check_in_date
                            )
                            if not planned_start:
                                continue

                            # Late Check-in
                            late_vals = self._calculate_late_checkin(
                                emp, attendance, local_punch_in, planned_start,
                                check_in_date, late_tolerance
                            )
                            if late_vals:
                                late_checkin_vals_list.append(late_vals)

                            # Overtime
                            overtime_vals = self._calculate_overtime(
                                emp, local_punch_out, planned_end,
                                check_out_date, overtime_tolerance
                            )
                            if overtime_vals:
                                overtime_vals_list.append(overtime_vals)

                        except Exception as e:
                            _logger.error(f"Error processing attendance {attendance.id}: {str(e)}")
                            continue

        # Batch create records
        if late_checkin_vals_list:
            self._cleanup_existing_late_checkins(late_checkin_vals_list)
            self.env['hr.late.checkin'].create(late_checkin_vals_list)
            _logger.info(f"Created {len(late_checkin_vals_list)} late check-in records")

        if overtime_vals_list:
            self._create_or_update_overtime(overtime_vals_list)
            _logger.info(f"Processed {len(overtime_vals_list)} overtime records")

    def _get_employee_schedule_for_date(self, employee, date):
        """
        Get the actual scheduled start/end time for an employee on a specific date.

        Args:
            employee: hr.employee record
            date: date object

        Returns:
            tuple: (planned_start_datetime, planned_end_datetime) or (None, None)
        """
        calendar = employee.resource_calendar_id
        if not calendar:
            return None, None

        # Handle flexible hours
        if employee.flexible_hours:
            return None, None

        # Get the weekday (0=Monday, 6=Sunday)
        weekday = str(date.weekday())

        # Search for matching attendance lines
        attendance_lines = calendar.attendance_ids.filtered(
            lambda att: att.dayofweek == weekday and
                        att.day_period != 'lunch' and
                        (not att.date_from or att.date_from <= date) and
                        (not att.date_to or att.date_to >= date)
        )

        if not attendance_lines:
            return None, None

        # Get company timezone
        company_tz = pytz.timezone(self.env.company.timezone or 'UTC')

        # Find morning/start and afternoon/end periods
        morning_att = attendance_lines.filtered(lambda a: a.day_period == 'morning')
        afternoon_att = attendance_lines.filtered(lambda a: a.day_period == 'afternoon')

        # Determine start time
        if morning_att:
            hour_from = morning_att[0].hour_from
        elif afternoon_att:
            hour_from = afternoon_att[0].hour_from
        else:
            hour_from = min(att.hour_from for att in attendance_lines)

        # Determine end time
        if afternoon_att:
            hour_to = afternoon_att[0].hour_to
        elif morning_att:
            hour_to = morning_att[0].hour_to
        else:
            hour_to = max(att.hour_to for att in attendance_lines)

        # Convert float hours to datetime
        planned_start = self._float_to_datetime(date, hour_from, company_tz)
        planned_end = self._float_to_datetime(date, hour_to, company_tz)

        return planned_start, planned_end

    # def _get_night_shift_schedule(self, company, local_punch_in, local_punch_out):
    #     """Get night shift schedule times."""
    #     night_shift_start = company.night_shift_start or 22.0
    #     night_shift_end = company.night_shift_end or 6.0
    #
    #     planned_start = local_punch_in.replace(
    #         hour=int(night_shift_start),
    #         minute=int((night_shift_start % 1) * 60),
    #         second=0,
    #         microsecond=0
    #     )
    #
    #     planned_end = local_punch_out.replace(
    #         hour=int(night_shift_end),
    #         minute=int((night_shift_end % 1) * 60),
    #         second=0,
    #         microsecond=0
    #     )
    #
    #     return planned_start, planned_end

    def _get_night_shift_schedule(self, company, local_punch_in, local_punch_out):
        """Get night shift schedule times."""
        night_shift_start = company.night_shift_start or 22.0
        night_shift_end = company.night_shift_end or 6.0

        planned_start = local_punch_in.replace(
            hour=int(night_shift_start),
            minute=int((night_shift_start % 1) * 60),
            second=0,
            microsecond=0
        )

        planned_end = local_punch_in.replace(
            hour=int(night_shift_end),
            minute=int((night_shift_end % 1) * 60),
            second=0,
            microsecond=0
        )

        # لو النهاية أقل من البداية، أضف يوم
        if planned_end <= planned_start:
            planned_end += timedelta(days=1)

        return planned_start, planned_end

    def _float_to_datetime(self, date, hour_float, timezone):
        """Convert float hour (e.g., 8.5) to datetime object."""
        hour = int(hour_float)
        minute = int((hour_float % 1) * 60)

        return timezone.localize(
            datetime.combine(date, datetime.min.time().replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0
            ))
        )

    def _calculate_late_checkin(self, employee, attendance, local_punch_in,
                                planned_start, check_in_date, tolerance_minutes):
        """
        Calculate late check-in duration with tolerance.

        Returns:
            dict: Late check-in values or None
        """
        if local_punch_in <= planned_start:
            return None

        late_duration_seconds = (local_punch_in - planned_start).total_seconds()
        late_duration_minutes = int(late_duration_seconds / 60)

        # Apply tolerance
        if late_duration_minutes <= tolerance_minutes:
            return None

        hours = late_duration_minutes // 60
        minutes = late_duration_minutes % 60

        return {
            'employee_id': employee.id,
            'attendance_id': attendance.id,
            'date': check_in_date,
            'late_duration': hours + (minutes / 60.0),
            'scheduled_start': planned_start.replace(tzinfo=None),
            'actual_start': local_punch_in.replace(tzinfo=None),
            'state': 'draft',
        }

    def _calculate_overtime(self, employee, local_punch_out, planned_end,
                            check_out_date, tolerance_minutes):
        """
        Calculate overtime duration with tolerance.

        Returns:
            dict: Overtime values or None
        """
        if not planned_end or local_punch_out <= planned_end:
            return None

        overtime_seconds = (local_punch_out - planned_end).total_seconds()
        overtime_minutes = int(overtime_seconds / 60)

        # Apply tolerance
        if overtime_minutes <= tolerance_minutes:
            return None

        hours = overtime_minutes // 60
        minutes = overtime_minutes % 60
        duration = hours + (minutes / 60.0)

        return {
            'employee_id': employee.id,
            'date': check_out_date,
            'duration': duration,
            'duration_real': duration,
        }

    def _cleanup_existing_late_checkins(self, late_checkin_vals_list):
        """Remove existing late check-in records to avoid duplicates."""
        for vals in late_checkin_vals_list:
            existing = self.env['hr.late.checkin'].search([
                ('employee_id', '=', vals['employee_id']),
                ('attendance_id', '=', vals['attendance_id'])
            ])
            if existing:
                existing.unlink()

    def _create_or_update_overtime(self, overtime_vals_list):
        """Create or update overtime records, accumulating same-day overtime."""
        for vals in overtime_vals_list:
            existing = self.env['hr.attendance.overtime'].search([
                ('employee_id', '=', vals['employee_id']),
                ('date', '=', vals['date'])
            ], limit=1)

            if existing:
                existing.unlink()
                # Accumulate overtime for same day
                # existing.write({
                #     'duration': existing.duration + vals['duration'],
                #     'duration_real': existing.duration_real + vals['duration_real'],
                # })
            self.env['hr.attendance.overtime'].create(vals)

    @api.model
    def unlink(self):
        for attendance in self:
            self.env['hr.attendance.overtime'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('date', '=', attendance.check_in.date() if attendance.check_in else False)
            ]).unlink()
        return super(Attendance, self).unlink()