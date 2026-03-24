# -*- coding: utf-8 -*-
{
    'name': 'HR Daily Presence Summary',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Track daily employee status (Attendance, Time Off, Weekend, etc.)',
    'author': 'DIGITS',
    'website': 'https://www.rpminerals.com',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_attendance',
        'hr_holidays',
        'hr_missions_module',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'wizards/hr_presence_summary_wizard_views.xml',
        'views/hr_presence_summary_views.xml',
        'reports/hr_presence_summary_report.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
