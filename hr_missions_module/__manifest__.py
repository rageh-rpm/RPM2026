{
    'name': 'HR Missions (hr_missions)',
    'version': '1.0.0',
    'summary': 'Manage employee missions, allowances and approvals',
    'category': 'Human Resources',
    'author': 'DIGITS',
    'license': 'LGPL-3',
    'depends': ['hr', 'hr_contract', 'hr_payroll', 'mail', 'account'],
    'data': [
        'data/sequence.xml',
        'security/hr_missions_security.xml',
        'security/ir.model.access.csv',
        'views/hr_mission_views.xml',
        'views/res_state.xml',
        'views/report.xml',


    ],
    'installable': True,
    'application': False,
}
