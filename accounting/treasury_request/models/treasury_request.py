# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class TreasuryRequest(models.Model):
    _name = 'treasury.request'
    _description = 'Treasury Payment Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    # ============================================
    # CORE FIELDS
    # ============================================

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('manager_approved', 'Manager Approved'),
        ('treasury_approved', 'Treasury Approved'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True, copy=False)

    # Request details
    request_type = fields.Selection([
        ('payment', 'Payment Request'),
        ('collection', 'Collection Request'),
    ], string='Type', required=True, default='payment', tracking=True)

    payment_category = fields.Selection([
        ('vendor', 'Vendor Payment'),
        ('employee', 'Employee Payment'),
        ('petty_cash', 'Petty Cash'),
        ('advance', 'Employee Advance'),
        ('loan', 'Loan Payment'),
        ('other', 'Other Payment'),
    ], string='Category', required=True, tracking=True)

    # Financial data
    partner_id = fields.Many2one(
        'res.partner',
        string='Payee',
        required=True,
        tracking=True,
        readonly=False,
        states={'confirmed': [('readonly', True)], 'rejected': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )

    partner_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Bank Account',
        domain="[('partner_id', '=', partner_id)]",
        tracking=True,
        readonly=False,
        states={'confirmed': [('readonly', True)], 'rejected': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )

    amount = fields.Monetary(
        string='Amount',
        required=True,
        tracking=True,
        readonly=False,
        states={'confirmed': [('readonly', True)], 'rejected': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True
    )

    description = fields.Text(
        string='Description',
        required=True,
        tracking=True,
        readonly=False,
        states={'confirmed': [('readonly', True)], 'rejected': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )

    # Scheduled execution
    scheduled_date = fields.Date(
        string='Requested Payment Date',
        default=fields.Date.today,
        required=True,
        tracking=True,
        readonly=False,
        states={'confirmed': [('readonly', True)], 'rejected': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )

    # Linked documents
    invoice_ids = fields.Many2many(
        'account.move',
        string='Related Invoices',
        domain="[('partner_id', '=', partner_id), ('move_type', 'in', ['in_invoice', 'in_refund']), ('state', '=', 'posted')]",
        readonly=False,
        states={'confirmed': [('readonly', True)], 'rejected': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    # ============================================
    # APPROVAL FIELDS
    # ============================================

    # Requester
    requester_id = fields.Many2one(
        'res.users',
        string='Requested By',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True
    )

    request_date = fields.Datetime(
        string='Request Date',
        default=fields.Datetime.now,
        readonly=True
    )

    # Manager approval (Stage 1)
    manager_id = fields.Many2one(
        'res.users',
        string='Direct Manager',
        compute='_compute_manager',
        store=True,
        tracking=True
    )

    manager_approved_date = fields.Datetime(
        string='Manager Approval Date',
        readonly=True,
        tracking=True
    )

    manager_approved_by = fields.Many2one(
        'res.users',
        string='Approved By (Manager)',
        readonly=True,
        tracking=True
    )

    manager_comments = fields.Text(
        string='Manager Comments',
        readonly=True
    )

    # Treasury approval (Stage 2)
    treasury_approved_date = fields.Datetime(
        string='Treasury Approval Date',
        readonly=True,
        tracking=True
    )

    treasury_approved_by = fields.Many2one(
        'res.users',
        string='Approved By (Treasury)',
        readonly=True,
        tracking=True
    )

    treasury_comments = fields.Text(
        string='Treasury Comments',
        readonly=True
    )

    # Treasury Executive data filling (Stage 3)
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        tracking=True,
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]"
    )

    payment_method_line_id = fields.Many2one(
        'account.payment.method.line',
        string='Payment Method',
        readonly=False,
        store=True,
        compute='_compute_payment_method_fields',
        domain="[('id', 'in', available_payment_method_line_ids)]",
        tracking=True
    )

    available_payment_method_line_ids = fields.Many2many(
        'account.payment.method.line',
        compute='_compute_payment_method_fields'
    )

    executive_confirmed_date = fields.Datetime(
        string='Executive Confirmation Date',
        readonly=True,
        tracking=True
    )

    executive_confirmed_by = fields.Many2one(
        'res.users',
        string='Confirmed By (Executive)',
        readonly=True,
        tracking=True
    )

    executive_comments = fields.Text(
        string='Executive Comments',
        readonly=True
    )

    # Rejection tracking
    rejected_by = fields.Many2one(
        'res.users',
        string='Rejected By',
        readonly=True,
        tracking=True
    )

    rejected_date = fields.Datetime(
        string='Rejection Date',
        readonly=True
    )

    rejection_reason = fields.Text(
        string='Rejection Reason',
        readonly=True,
        tracking=True
    )

    # ============================================
    # PAYMENT LINK
    # ============================================

    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        readonly=True,
        copy=False,
        ondelete='restrict'
    )

    payment_state = fields.Selection(
        related='payment_id.state',
        string='Payment Status',
        store=True
    )

    # ============================================
    # COMPUTE METHODS
    # ============================================

    @api.depends('requester_id')
    def _compute_manager(self):
        """Get manager from employee record"""
        for rec in self:
            if rec.requester_id:
                employee = self.env['hr.employee'].search([
                    ('user_id', '=', rec.requester_id.id),
                    ('company_id', '=', rec.company_id.id)
                ], limit=1)

                if employee and employee.parent_id and employee.parent_id.user_id:
                    rec.manager_id = employee.parent_id.user_id
                else:
                    rec.manager_id = False
            else:
                rec.manager_id = False

    @api.depends('journal_id', 'request_type')
    def _compute_payment_method_fields(self):
        """Calculate available payment methods based on journal and request type"""
        for rec in self:
            if rec.journal_id and rec.request_type:
                # Determine payment type based on request type
                payment_type = 'outbound' if rec.request_type == 'payment' else 'inbound'

                # Get available payment method lines
                available_lines = rec.journal_id._get_available_payment_method_lines(payment_type)

                rec.available_payment_method_line_ids = available_lines

                # Clear previous selection if not in available lines
                if rec.payment_method_line_id and rec.payment_method_line_id not in available_lines:
                    rec.payment_method_line_id = False
            else:
                rec.available_payment_method_line_ids = False
                rec.payment_method_line_id = False

    # ============================================
    # CONSTRAINTS
    # ============================================

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))

    # ============================================
    # ORM METHODS
    # ============================================

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate sequence on create"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('treasury.request') or _('New')

        records = super().create(vals_list)

        # Subscribe requester and manager
        for record in records:
            record.message_subscribe(partner_ids=[record.requester_id.partner_id.id])
            if record.manager_id:
                record.message_subscribe(partner_ids=[record.manager_id.partner_id.id])

        return records

    def unlink(self):
        """Prevent deletion of non-draft requests"""
        for rec in self:
            if rec.state not in ['draft', 'cancelled', 'rejected']:
                raise UserError(_('You cannot delete a request that is in progress. Please cancel it first.'))
        return super().unlink()

    # ============================================
    # WORKFLOW ACTIONS
    # ============================================

    def action_submit(self):
        """Stage 0 → 1: User submits request to manager"""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requests can be submitted.'))

            # Validate required fields
            rec._validate_submission()

            # Check manager exists
            if not rec.manager_id:
                raise UserError(_('No manager assigned. Please contact HR to set up your reporting line.'))

            rec.write({'state': 'submitted'})

            # Send notification to manager
            rec._notify_manager()

            # Post message
            rec.message_post(
                body=_('Request submitted by %s for manager approval.', rec.requester_id.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def action_manager_approve(self):
        """Stage 1 → 2: Manager approves and sends to treasury"""
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted requests can be approved by manager.'))

            # Check user is the assigned manager
            if self.env.user != rec.manager_id and not self.env.user.has_group('treasury_request.group_treasury_admin'):
                raise UserError(_('Only the assigned manager can approve this request.'))

            rec.write({
                'state': 'manager_approved',
                'manager_approved_by': self.env.user.id,
                'manager_approved_date': fields.Datetime.now(),
            })

            # Notify treasury group
            rec._notify_treasury_team()

            rec.message_post(
                body=_('Approved by manager %s. Sent to Treasury.', self.env.user.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def action_manager_reject(self):
        """Stage 1 → Rejected: Manager rejects request"""
        return self._open_rejection_wizard('manager')

    def action_treasury_approve(self):
        """Stage 2 → 3: Treasury approves and sends to executive"""
        for rec in self:
            if rec.state != 'manager_approved':
                raise UserError(_('Request must be manager-approved first.'))

            # Check user is in treasury group
            if not self.env.user.has_group('treasury_request.group_treasury_officer'):
                raise UserError(_('Only Treasury Officers can approve requests.'))

            rec.write({
                'state': 'treasury_approved',
                'treasury_approved_by': self.env.user.id,
                'treasury_approved_date': fields.Datetime.now(),
            })

            # Notify treasury executives
            rec._notify_treasury_executives()

            rec.message_post(
                body=_('Approved by treasury officer %s. Ready for execution.', self.env.user.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def action_treasury_reject(self):
        """Stage 2 → Rejected: Treasury rejects request"""
        return self._open_rejection_wizard('treasury')

    def action_executive_confirm(self):
        """Stage 3 → Confirmed: Executive fills data and confirms"""
        for rec in self:
            if rec.state != 'treasury_approved':
                raise UserError(_('Request must be treasury-approved first.'))

            # Check user is treasury executive
            if not self.env.user.has_group('treasury_request.group_treasury_exec'):
                raise UserError(_('Only Treasury Executives can confirm execution.'))

            # CRITICAL: Validate executive has filled required data
            rec._validate_executive_data()

            # Create and post payment
            payment = rec._create_and_post_payment()

            # Update request state
            rec.write({
                'state': 'confirmed',
                'executive_confirmed_by': self.env.user.id,
                'executive_confirmed_date': fields.Datetime.now(),
                'payment_id': payment.id,
            })

            rec.message_post(
                body=_('Payment created and posted by %s. Payment: %s', self.env.user.name, payment.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

            # Notify requester
            rec._notify_requester_completed()

        # Open created payment
        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        """Cancel request"""
        for rec in self:
            if rec.state == 'confirmed':
                raise UserError(_('Cannot cancel a confirmed payment. Please cancel the payment record first.'))

            rec.write({'state': 'cancelled'})

            rec.message_post(
                body=_('Request cancelled by %s.', self.env.user.name),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def action_set_to_draft(self):
        """Reset to draft"""
        for rec in self:
            if rec.state not in ['cancelled', 'rejected']:
                raise UserError(_('Only cancelled or rejected requests can be reset to draft.'))

            if rec.payment_id:
                raise UserError(_('Cannot reset to draft as payment already exists.'))

            rec.write({
                'state': 'draft',
                'rejected_by': False,
                'rejected_date': False,
                'rejection_reason': False,
            })

    def action_view_payment(self):
        """Open related payment"""
        self.ensure_one()

        if not self.payment_id:
            raise UserError(_('No payment linked to this request.'))

        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ============================================
    # VALIDATION METHODS
    # ============================================

    def _validate_submission(self):
        """Validate request before submission"""
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_('Payee is required.'))

        if self.amount <= 0:
            raise UserError(_('Amount must be greater than zero.'))

        if not self.description:
            raise UserError(_('Description is required.'))

        if not self.payment_category:
            raise UserError(_('Payment category is required.'))

    def _validate_executive_data(self):
        """Validate executive has filled journal and payment method"""
        self.ensure_one()

        if not self.journal_id:
            raise UserError(_('Payment Journal is required before confirmation.'))

        if not self.payment_method_line_id:
            raise UserError(_('Payment Method is required before confirmation.'))

    # ============================================
    # PAYMENT CREATION
    # ============================================

    def _create_and_post_payment(self):
        """Create account.payment and immediately post it"""
        self.ensure_one()

        # Prepare payment values
        payment_vals = self._prepare_payment_vals()

        # Create payment
        payment = self.env['account.payment'].with_context(
            default_treasury_request_id=self.id
        ).create(payment_vals)

        # IMMEDIATELY POST THE PAYMENT (creates journal entries)
        payment.action_post()

        return payment

    def _prepare_payment_vals(self):
        """Map request fields to payment fields"""
        self.ensure_one()

        # Determine payment type
        payment_type = 'outbound' if self.request_type == 'payment' else 'inbound'

        # Determine partner type
        partner_type = 'supplier'  # Default for payments
        if self.request_type == 'collection':
            partner_type = 'customer'

        vals = {
            'payment_type': payment_type,
            'partner_type': partner_type,
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'date': self.scheduled_date or fields.Date.today(),
            'memo': '%s - %s' % (self.name, self.description[:50]),
            'journal_id': self.journal_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'treasury_request_id': self.id,
        }

        # Add bank account if specified
        if self.partner_bank_id:
            vals['partner_bank_id'] = self.partner_bank_id.id

        return vals

    # ============================================
    # REJECTION HANDLING
    # ============================================

    def _open_rejection_wizard(self, rejection_stage):
        """Open wizard to capture rejection reason"""
        return {
            'name': _('Reject Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'treasury.request.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_rejection_stage': rejection_stage,
            }
        }

    def action_reject(self, reason):
        """Mark request as rejected with reason"""
        self.ensure_one()

        self.write({
            'state': 'rejected',
            'rejected_by': self.env.user.id,
            'rejected_date': fields.Datetime.now(),
            'rejection_reason': reason,
        })

        self.message_post(
            body=_('Request rejected by %s.<br/>Reason: %s', self.env.user.name, reason),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

        # Notify requester
        self._notify_requester_rejected()

    # ============================================
    # NOTIFICATION METHODS
    # ============================================

    def _notify_manager(self):
        """Send notification to manager"""
        self.ensure_one()

        if self.manager_id:
            self.activity_schedule(
                'treasury_request.mail_activity_treasury_approval',
                user_id=self.manager_id.id,
                summary=_('Payment Request: %s', self.name),
                note=_('Please review payment request for %s - %s %s',
                       self.partner_id.name,
                       self.amount,
                       self.currency_id.name)
            )

    def _notify_treasury_team(self):
        """Notify treasury officers"""
        treasury_group = self.env.ref('treasury_request.group_treasury_officer', raise_if_not_found=False)

        if treasury_group:
            for user in treasury_group.users:
                self.activity_schedule(
                    'treasury_request.mail_activity_treasury_approval',
                    user_id=user.id,
                    summary=_('Payment Request: %s', self.name),
                    note=_('Manager approved. Please review: %s - %s %s',
                           self.partner_id.name,
                           self.amount,
                           self.currency_id.name)
                )

    def _notify_treasury_executives(self):
        """Notify treasury executives"""
        exec_group = self.env.ref('treasury_request.group_treasury_exec', raise_if_not_found=False)

        if exec_group:
            for user in exec_group.users:
                self.activity_schedule(
                    'treasury_request.mail_activity_treasury_execution',
                    user_id=user.id,
                    summary=_('Payment Ready: %s', self.name),
                    note=_('Please execute payment: %s - %s %s',
                           self.partner_id.name,
                           self.amount,
                           self.currency_id.name)
                )

    def _notify_requester_completed(self):
        """Notify requester that payment is completed"""
        self.ensure_one()

        self.message_post(
            body=_('Your payment request has been executed. Payment reference: %s', self.payment_id.name),
            partner_ids=[self.requester_id.partner_id.id],
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )

    def _notify_requester_rejected(self):
        """Notify requester of rejection"""
        self.ensure_one()

        self.message_post(
            body=_('Your payment request was rejected.<br/>Reason: %s', self.rejection_reason),
            partner_ids=[self.requester_id.partner_id.id],
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )
