from odoo import fields, models, api
import json
import requests


class Department(models.Model):
    _inherit = 'hr.department'

    biotime_department_id = fields.Char()

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

