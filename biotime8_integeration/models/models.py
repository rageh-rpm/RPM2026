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
