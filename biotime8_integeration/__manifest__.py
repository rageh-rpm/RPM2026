# -*- coding: utf-8 -*-
{
    'name': "biotime8_integeration",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "M.Rageh",
    'website': "https://www.rpminerals.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','hr','hr_attendance','hr_holidays'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'wizard/load_punches_wizard.xml',
        'views/hr_employee.xml',
        'views/hr_department.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
