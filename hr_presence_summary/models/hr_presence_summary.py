# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, time, timedelta
import pytz

class HrPresenceSummary(models.Model):
    _name = 'hr.presence.summary'
    _description = 'HR Daily Presence Summary'
    _order = 'date desc, employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True, ondelete='cascade')
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', string='Department', store=True, index=True)
    date = fields.Date(string='Date', required=True, index=True)
    presence_type = fields.Selection([
        ('attendance', 'Attendance'),
        ('time_off', 'Time Off'),
        ('mission', 'Mission'),
        ('holiday', 'Public Holiday'),
        ('weekend', 'Weekend'),
        ('absent', 'Absence'),
        ('other', 'Other'),
    ], string='Status', required=True, index=True)
    
    leave_type_id = fields.Many2one('hr.leave.type', string='Time Off Type')
    hours = fields.Float(string='Duration (Hours)', default=0.0)
    duration_display = fields.Char(string='Duration')
    description = fields.Text(string='Description')
    
    source_model = fields.Char(string='Source Model')
    source_id = fields.Integer(string='Source ID')
    source_ref = fields.Reference(selection=[
        ('hr.leave', 'Time Off'), 
        ('hr.attendance', 'Attendance')
    ], string='Source Record', compute='_compute_source_ref')

    @api.depends('source_model', 'source_id')
    def _compute_source_ref(self):
        for rec in self:
            if rec.source_model and rec.source_id:
                rec.source_ref = '%s,%s' % (rec.source_model, rec.source_id)
            else:
                rec.source_ref = False

    @property
    def shorthand_status(self):
        mapping = {
            'attendance': 'A',
            'time_off': 'L',
            'mission': 'M',
            'holiday': 'H',
            'weekend': 'W',
            'absent': 'X',
        }
        status = mapping.get(self.presence_type, '?')
        if self.presence_type == 'time_off' and self.leave_type_id:
            # Use first letter of leave type or just 'L'
            return 'L(%s)' % self.leave_type_id.name[:2]
        return status
    _sql_constraints = [
        ('unique_attendance_source', 'unique(employee_id, date, source_model, source_id)', 
         'A duplicate summary record for the same source already exists!')
    ]

    def action_generate_summaries(self, date_from, date_to, employee_ids=None):
        """
        Generates daily status records for the given range and employees.
        """
        if not employee_ids:
            employee_ids = self.env['hr.employee'].search([('active', '=', True)])
        else:
            employee_ids = self.env['hr.employee'].browse(employee_ids)

        # 1. Check for pending leaves
        pending_leaves = self.env['hr.leave'].search([
            ('employee_id', 'in', employee_ids.ids),
            ('date_from', '<=', fields.Datetime.to_string(datetime.combine(date_to, time.max))),
            ('date_to', '>=', fields.Datetime.to_string(datetime.combine(date_from, time.min))),
            ('state', 'in', ['confirm'])
        ])
        if pending_leaves:
            msg = _("There are pending time-offs that need to be confirmed or cancelled:\n")
            for leave in pending_leaves:
                msg += _("- %s: %s to %s\n") % (leave.employee_id.name, leave.date_from, leave.date_to)
            raise UserError(msg)

        # 2. Process each day and employee
        current_date = date_from
        while current_date <= date_to:
            start_dt = datetime.combine(current_date, time.min)
            end_dt = datetime.combine(current_date, time.max)
            
            for employee in employee_ids:
                # Remove existing automated records for this day (keep manually created ones if any? 
                # For now let's just delete records with source_model info)
                self.search([
                    ('employee_id', '=', employee.id),
                    ('date', '=', current_date),
                ]).unlink()

                found_activity = False

                # A. Check Time Off (Validated)
                leaves = self.env['hr.leave'].search([
                    ('employee_id', '=', employee.id),
                    ('date_from', '<=', fields.Datetime.to_string(end_dt)),
                    ('date_to', '>=', fields.Datetime.to_string(start_dt)),
                    ('state', '=', 'validate')
                ])
                for leave in leaves:
                    # Calculate overlapping hours or days
                    duration_str = ""
                    if leave.request_unit_hours:
                        duration_str = _("%g hours") % leave.number_of_hours_display
                    else:
                        start_date = leave.date_from.date()
                        current_day_num = (current_date - start_date).days + 1
                        total_days = int(leave.number_of_days)
                        if total_days > 1:
                            duration_str = _("Day %d of %d") % (current_day_num, total_days)
                        else:
                            duration_str = _("1 day")

                    self.create({
                        'employee_id': employee.id,
                        'date': current_date,
                        'presence_type': 'time_off',
                        'leave_type_id': leave.holiday_status_id.id,
                        'hours': leave.number_of_hours_display if leave.request_unit_hours else 8.0,
                        'duration_display': duration_str,
                        'source_model': 'hr.leave',
                        'source_id': leave.id,
                        'description': leave.name or leave.holiday_status_id.name
                    })
                    found_activity = True

                # B. Check Missions (Approved/Paid)
                missions = self.env['hr.mission'].search([
                    ('employee_id', '=', employee.id),
                    ('start_datetime', '<=', fields.Datetime.to_string(end_dt)),
                    ('end_datetime', '>=', fields.Datetime.to_string(start_dt)),
                    ('state', 'in', ['approved', 'paid'])
                ])
                for mission in missions:
                    start_date = mission.start_datetime.date()
                    current_day_num = (current_date - start_date).days + 1
                    total_days = int(mission.duration_days)
                    duration_str = ""
                    if total_days > 1:
                        duration_str = _("Day %d of %d") % (current_day_num, total_days)
                    else:
                        duration_str = _("1 day")

                    self.create({
                        'employee_id': employee.id,
                        'date': current_date,
                        'presence_type': 'mission',
                        'hours': mission.duration_hours / mission.duration_days if mission.duration_days else 8.0,
                        'duration_display': duration_str,
                        'source_model': 'hr.mission',
                        'source_id': mission.id,
                        'description': mission.mission_purpose or _('Mission')
                    })
                    found_activity = True

                # C. Check Attendance
                attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '<=', fields.Datetime.to_string(end_dt)),
                    '|', ('check_out', '>=', fields.Datetime.to_string(start_dt)), ('check_out', '=', False)
                ])
                for att in attendances:
                    self.create({
                        'employee_id': employee.id,
                        'date': current_date,
                        'presence_type': 'attendance',
                        'hours': att.worked_hours,
                        'duration_display': _("%g hours") % att.worked_hours if att.worked_hours else "",
                        'source_model': 'hr.attendance',
                        'source_id': att.id,
                        'description': _('Attendance: %s') % (att.check_in.strftime('%H:%M') if att.check_in else '')
                    })
                    found_activity = True

                # C. If no activity, check Resource Calendar (Weekend/Holiday)
                if not found_activity:
                    calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
                    if calendar:
                        dayofweek = str(current_date.weekday())
                        # Check if it's a working day
                        working_hours = calendar.attendance_ids.filtered(lambda a: a.dayofweek == dayofweek)
                        
                        # Check for global leaves (Holidays)
                        global_leaves = calendar.global_leave_ids.filtered(
                            lambda l: l.date_from.date() <= current_date <= l.date_to.date()
                        )
                        
                        if global_leaves:
                            self.create({
                                'employee_id': employee.id,
                                'date': current_date,
                                'presence_type': 'holiday',
                                'duration_display': _("1 day"),
                                'hours': 0.0,
                                'description': global_leaves[0].name
                            })
                        elif not working_hours:
                            self.create({
                                'employee_id': employee.id,
                                'date': current_date,
                                'presence_type': 'weekend',
                                'duration_display': _("1 day"),
                                'hours': 0.0,
                                'description': _('Weekend')
                            })
                        else:
                            # It's a working day but no attendance/leave found
                            self.create({
                                'employee_id': employee.id,
                                'date': current_date,
                                'presence_type': 'absent',
                                'duration_display': _("1 day"),
                                'hours': 0.0,
                                'description': _('No presence recorded')
                            })

            current_date += timedelta(days=1)
        return True
