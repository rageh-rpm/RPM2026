# -*- coding: utf-8 -*-
{
    'name': 'Treasury Payment Request',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Manage payment requests with multi-level approval workflow',
    'description': '''
        Treasury Payment Request Management
        ====================================

        Complete payment request workflow with multi-level approvals:

        Key Features:
        -------------
        * **Three-Stage Approval Workflow**:
          - Manager Approval (direct manager from HR)
          - Treasury Officer Approval
          - Treasury Executive Execution

        * **Payment Request Management**:
          - Create payment/collection requests
          - Link to vendor invoices for reconciliation
          - Multiple payment categories (Vendor, Employee, Petty Cash, Advance, Loan, Other)
          - Multi-currency support
          - Scheduled payment dates

        * **Automatic Payment Creation**:
          - Seamless integration with account.payment
          - Auto-create and post payments on executive confirmation
          - Link payments back to treasury requests

        * **Communication & Tracking**:
          - Email notifications at each approval stage
          - Activity tracking and reminders
          - Rejection workflow with reason capture
          - Full audit trail with chatter integration

        * **Security & Access Control**:
          - Role-based access (User, Manager, Officer, Executive, Admin)
          - Record rules for data isolation
          - Manager can only approve their team's requests
          - Treasury sees all requests

        * **User-Friendly Interface**:
          - Kanban view for mobile-friendly access
          - Smart filters and grouping
          - Status badges and color coding
          - Quick access to pending approvals

        Workflow Summary:
        -----------------
        1. User creates draft request
        2. User submits to direct manager
        3. Manager approves/rejects
        4. Treasury Officer approves/rejects
        5. Treasury Executive fills journal & payment method
        6. Executive confirms → Payment auto-created & posted

        Technical Details:
        ------------------
        * Compatible with Odoo 18 Enterprise Edition
        * Fully integrated with accounting module
        * Uses HR module for manager hierarchy
        * Chatter and activity tracking enabled
        * Multi-company ready
    ''',
    'author': 'Digital information Solutions (Digits)',
    'website': 'https://www.digits-tech.com',
    'license': 'LGPL-3',

    # Dependencies
    'depends': [
        'account',  # For payment integration
        'hr',  # For manager hierarchy
        'mail',  # For chatter and activities
    ],

    # Data files - order matters!
    'data': [
        # Security (must be first)
        'security/security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/sequence_data.xml',
        'data/mail_activity_data.xml',
        'data/mail_template_data.xml',

        # Views
        'views/treasury_request_views.xml',
        'views/account_payment_views.xml',
        'views/treasury_menu.xml',
        'report/report.xml',

        # Wizards
        'wizards/treasury_request_reject_wizard_views.xml',
    ],

    # Demo data (optional)
    'demo': [
        # 'demo/demo_data.xml',
    ],

    # Assets (if you add JS/CSS later)
    'assets': {
        # 'web.assets_backend': [
        #     'treasury_request/static/src/js/**/*',
        #     'treasury_request/static/src/css/**/*',
        # ],
    },

    # Module metadata
    'installable': True,
    'application': True,
    'auto_install': False,

    # Module images
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],

    # Pricing (if you plan to sell on Odoo Apps Store)
    'price': 0.00,
    'currency': 'EUR',

    # External dependencies (if any)
    'external_dependencies': {
        'python': [],
        'bin': [],
    },

    # Post-install message
    'post_init_hook': None,
    'uninstall_hook': None,
}
