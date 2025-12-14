# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json
import requests

class BiotimeConnection(models.Model):
    _name= 'biotime.connection'
    description = 'BioTime User Auth. Screen'

    name = fields.Char()
    password = fields.Char()
    auth_code = fields.Char()
    is_active = fields.Boolean()

    def generate_auth(self):
        for rec in self:
            url = "http://172.20.10.11/jwt-api-token-auth/"
            headers = {
                "Content-Type": "application/json",
            }
            data = {
                "username": rec.name,
                "password": rec.password,
            }

            response = requests.post(url, data=json.dumps(data), headers=headers)
            if response.status_code == 200:
                resp_auth_code = response.json()
                auth_txt = resp_auth_code['token']
                rec.auth_code = "JWT "+auth_txt

                # print(auth_txt)

class BioIntegeration(models.Model):
    _name = 'biotime.integeration'
    _description = 'biotime8_integeration.biotime8_integeration'

    name = fields.Char()

    def rec_print(self):
        for rec in self:
            auth_rec = self.env['biotime.connection'].search([('is_active','=',True)],limit=1)

            url = "http://172.20.10.11/personnel/api/employees/"
            # use General token
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_rec.auth_code,
            }
            response = requests.get(url, headers=headers)
            print(response.text)



class BiotimePunch(models.Model):
    _name = "biotime.punch"
    _description = "BioTime Raw Punch"
    _order = "punch_time desc"

    # Technical / identification fields
    name = fields.Char(string="Punch Reference", readonly=True)
    emp_code = fields.Char(string="Employee Code", index=True, required=True)

    # HR linkage
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        ondelete='cascade',
        index=True,
        help="Linked Odoo employee for this punch."
    )

    # Biotime payload fields
    first_name = fields.Char(string="First Name")
    last_name = fields.Char(string="Last Name")
    department = fields.Char(string="Department (Biotime)")
    punch_time = fields.Datetime(string="Punch Time", required=True, index=True)
    punch_state_display = fields.Char(string="Punch State")
    verify_type_display = fields.Char(string="Verification Type")
    terminal_alias = fields.Char(string="Terminal Alias")

    # Optional raw JSON if you want to debug/trace Biotime payloads
    raw_payload = fields.Json(string="Raw Payload", help="Original JSON from Biotime, for debugging.")

    _sql_constraints = [
        # Prevent duplicate punches from being stored twice
        (
            'biotime_punch_unique',
            'unique(emp_code, punch_time, terminal_alias)',
            'Biotime punch already exists for this employee, time, and terminal!'
        ),
    ]

    def name_get(self):
        """User-friendly display name."""
        result = []
        for rec in self:
            label = rec.punch_time and rec.punch_time.strftime('%Y-%m-%d %H:%M:%S') or 'Unknown'
            if rec.emp_code:
                label = f"{rec.emp_code} - {label}"
            result.append((rec.id, label))
        return result
