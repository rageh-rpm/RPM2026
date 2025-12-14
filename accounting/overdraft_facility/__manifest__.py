# -*- coding: utf-8 -*-
{
    'name': 'Overdraft Facility Management',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Manage bank overdraft facilities with credit limits and settlements',
    'description': """
        Overdraft Facility Management
        ==============================
        * Create overdraft facilities with time periods
        * Set credit limits per facility
        * Track payments and settlements
        * Prevent overlapping facilities
        * Monitor utilization amounts
        * Dashboard with key metrics
    """,
    'author': 'Digital Information Solutions (Digits)',
    'website': 'https://www.digits-tech.com',
    'depends': [
        'account',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/cron.xml',
        'views/overdraft_facility_views.xml',
        'views/overdraft_settlement_views.xml',
        'views/account_journal_views.xml',
        'views/overdraft_settlement_allocation_views.xml',
        'views/overdraft_interest_rate_history_views.xml',
        'views/account_payment_views.xml',
        'views/overdraft_interest_accrual_views.xml',

        'views/menu_views.xml',

        'wizards/overdraft_rate_change_wizard_views.xml',
        'wizards/overdraft_settlement_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
