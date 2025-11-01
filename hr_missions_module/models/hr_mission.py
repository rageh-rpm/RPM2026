from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class HrMission(models.Model):
    _name = 'hr.mission'
    _description = 'HR Mission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Fields
    name = fields.Char(string='Reference', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('employee.mission') or '/')
    description = fields.Text(string='Mission Description', tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    country_id = fields.Many2one('res.country',default=lambda self: self.env.company.country_id)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  tracking=True, default=lambda self: self._default_employee())
    manager_id = fields.Many2one('hr.employee', string='Manager', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department')
    start_datetime = fields.Datetime(string='Start DateTime', required=True, tracking=True)
    end_datetime = fields.Datetime(string='End DateTime', required=True, tracking=True)
    duration_days = fields.Float(string='Duration (Days)', compute='_compute_duration', store=True)

    type_id = fields.Many2one('hr.mission.type', string='Mission Type', required=True)
    scope = fields.Selection([('in_country', 'In Country'), ('abroad', 'Abroad')],
                             default='in_country', required=True, tracking=True)

    state_id = fields.Many2one('res.country.state', string='State', required=True)
    distance_km = fields.Float(string='Distance (km)', compute='_compute_distance_fare', store=True)
    fixed_fare = fields.Float(string='Fixed Fare', compute='_compute_distance_fare', store=True,
                              currency_field='company_currency_id')
    company_currency_id = fields.Many2one('res.currency', related='type_id.currency_id', readonly=True)

    accommodation = fields.Boolean(string='Accommodation Required')
    accommodation_type_id = fields.Many2one('hr.mission.accommodation.type', string='Accommodation Type')
    transportation = fields.Boolean(string='Transportation Required')
    transportation_type_id = fields.Many2one('hr.mission.transport.type', string='Transportation Type')

    allowance_line_ids = fields.One2many('hr.mission.allowance', 'mission_id',
                                         string='Allowance Lines', tracking=True)
    grand_total = fields.Monetary(string='Grand Total', compute='_compute_grand_total',
                                  store=True, currency_field='company_currency_id')

    # Status and workflow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_manager', 'Pending Manager Approval'),
        ('to_sector_head', 'Pending Sector Head'),
        ('to_hr', 'Pending HR Approval'),
        ('to_finance', 'Pending Finance Approval'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected')
    ], default='draft', tracking=True)

    requested_by = fields.Many2one('res.users', string='Requested By',
                                   default=lambda self: self.env.user, tracking=True)
    approved_by_manager = fields.Many2one('res.users', string='Approved by Manager', readonly=True)
    approved_by_sector_head = fields.Many2one('res.users', string='Approved by Sector Head', readonly=True)
    approved_by_hr = fields.Many2one('res.users', string='Approved by HR', readonly=True)
    approved_by_finance = fields.Many2one('res.users', string='Approved by Finance', readonly=True)

    # Additional fields for better tracking
    rejection_reason = fields.Text(string='Rejection Reason')
    mission_purpose = fields.Text(string='Mission Purpose', required=True)
    expected_outcomes = fields.Text(string='Expected Outcomes')

    # Computed fields for UI
    can_edit = fields.Boolean(compute='_compute_can_edit')
    is_manager = fields.Boolean(compute='_compute_is_manager')

    # Default methods
    @api.model
    def _default_employee(self):
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        return employee.id if employee else False


    # def _expand_states(self, states, domain, order):
    #     # Always return all states in your selection field, preserving order
    #     return [key for key, val in self._fields['state'].selection]

    # Compute methods
    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime:
                start_dt = fields.Datetime.from_string(rec.start_datetime)
                end_dt = fields.Datetime.from_string(rec.end_datetime)
                if end_dt >= start_dt:
                    duration = end_dt - start_dt
                    rec.duration_days = duration.total_seconds() / (24 * 3600)
                else:
                    rec.duration_days = 0
            else:
                rec.duration_days = 0

    @api.depends('state_id', 'scope')
    def _compute_distance_fare(self):
        for rec in self:
            if rec.state_id:
                rec.distance_km = rec.state_id.distance_km
                rec.fixed_fare = rec.state_id.fixed_fare
            else:
                rec.distance_km = 0
                rec.fixed_fare = 0

    @api.depends('allowance_line_ids.total_amount')
    def _compute_grand_total(self):
        for rec in self:
            rec.grand_total = sum(rec.allowance_line_ids.mapped('total_amount'))

    # For can_edit - since it depends on current user, we'll use minimal dependencies
    @api.depends('state', 'requested_by')
    def _compute_can_edit(self):
        current_user = self.env.user
        for rec in self:
            rec.can_edit = (
                    rec.state in ['draft', 'rejected'] and
                    rec.requested_by == current_user
            )

    # For is_manager - optimized version
    @api.depends('employee_id.parent_id')
    def _compute_is_manager(self):
        # Get current user's employee record once outside the loop
        current_employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )

        for rec in self:
            rec.is_manager = bool(
                current_employee and
                rec.employee_id.parent_id and
                current_employee.id == rec.employee_id.parent_id.id
            )
    # Constraints and validations
    @api.constrains('start_datetime', 'end_datetime')
    def _check_dates(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime:
                start_dt = fields.Datetime.from_string(rec.start_datetime)
                end_dt = fields.Datetime.from_string(rec.end_datetime)
                if end_dt <= start_dt:
                    raise ValidationError("End datetime must be after start datetime")

                # Check if mission duration is reasonable (e.g., not more than 1 year)
                max_duration = timedelta(days=365)
                if (end_dt - start_dt) > max_duration:
                    raise ValidationError("Mission duration cannot exceed 1 year")

    @api.constrains('employee_id', 'manager_id')
    def _check_manager_employee(self):
        for rec in self:
            if rec.manager_id and rec.employee_id:
                if rec.manager_id.id == rec.employee_id.id:
                    raise ValidationError("Employee cannot be their own manager")

    # Onchange methods
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id
            self.manager_id = self.employee_id.parent_id

    @api.onchange('type_id', 'accommodation_type_id', 'transportation_type_id', 'scope', 'state_id','duration_days')
    def _onchange_generate_allowances(self):
        for rec in self:
            if rec.state in ['draft', 'rejected']:
                lines = []

                # Clear existing lines
                rec.allowance_line_ids = [(5, 0, 0)]

                # Add accommodation allowance
                if (rec.accommodation and rec.accommodation_type_id and
                        rec.accommodation_type_id.apply_allowance):
                    amt = (rec.accommodation_type_id.fixed_amount_abroad
                           if rec.scope == 'abroad'
                           else rec.accommodation_type_id.fixed_amount_in_country)
                    if amt > 0:
                        lines.append((0, 0, {
                            'name': f'Accommodation - {rec.accommodation_type_id.name}',
                            'allowance_type': 'accommodation',
                            'amount': amt,
                            'quantity': rec.duration_days or 1,
                            'total_amount': amt * (rec.duration_days or 1)
                        }))

                # Add transportation allowance
                if (rec.transportation and rec.transportation_type_id and rec.transportation_type_id.apply_allowance):
                    amt =0
                    if rec.scope == 'abroad':
                            amt= rec.transportation_type_id.fixed_amount_abroad
                    else:
                        if not rec.transportation_type_id.personal_vehicle:
                                amt = rec.state_id.fixed_fare
                        else:
                                amt = rec.transportation_type_id.fixed_amount_in_country*rec.state_id.distance_km

                    if amt > 0:
                        lines.append((0, 0, {
                            'name': f'Transportation - {rec.transportation_type_id.name}',
                            'allowance_type': 'transportation',
                            'amount': amt,
                            'quantity': 1,
                            'total_amount': amt
                        }))

                # Add fixed fare for in-country missions
                if rec.scope == 'in_country' and rec.fixed_fare and rec.fixed_fare > 0:
                    lines.append((0, 0, {
                        'name': f'Fixed Fare - {rec.state_id.name}',
                        'allowance_type': 'fixed_fare',
                        'amount': rec.fixed_fare,
                        'quantity': 1,
                        'total_amount': rec.fixed_fare
                    }))

                # Add daily allowance based on mission type
                if rec.type_id and rec.type_id.daily_allowance > 0 and rec.duration_days > 0:
                    daily_amt = rec.type_id.daily_allowance
                    total_daily = daily_amt * rec.duration_days
                    lines.append((0, 0, {
                        'name': f'Daily Allowance - {rec.type_id.name}',
                        'allowance_type': 'daily',
                        'amount': daily_amt,
                        'quantity': rec.duration_days,
                        'total_amount': total_daily
                    }))

                rec.allowance_line_ids = lines

    # Action methods with validations
    def action_request_manager(self):
        for rec in self:
            if not rec.manager_id:
                raise UserError("Please set a manager before requesting approval")

            if not rec.start_datetime or not rec.end_datetime:
                raise UserError("Please set both start and end datetime")

            if not rec.mission_purpose:
                raise UserError("Please provide mission purpose")

            rec._check_dates()  # Re-validate dates

            rec.state = 'to_manager'
            rec.message_post(body="Mission request submitted for manager approval")

    def action_approve_manager(self):
        for rec in self:
            if not self.env.user.has_group('hr.group_hr_manager'):
                raise UserError("Only managers can perform this action")

            rec.approved_by_manager = self.env.user
            rec.state = 'to_sector_head'
            rec.message_post(body=f"Mission approved by manager: {self.env.user.name}")

    def action_approve_sector_head(self):
        for rec in self:
            rec.approved_by_sector_head = self.env.user
            rec.state = 'to_hr'
            rec.message_post(body=f"Mission approved by sector head: {self.env.user.name}")

    def action_approve_hr(self):
        for rec in self:
            if not self.env.user.has_group('hr.group_hr_user'):
                raise UserError("Only HR users can perform this action")

            rec.approved_by_hr = self.env.user
            rec.state = 'to_finance'
            rec.message_post(body=f"Mission approved by HR: {self.env.user.name}")

    def action_approve_finance(self):
        for rec in self:
            if not self.env.user.has_group('account.group_account_user'):
                raise UserError("Only finance users can perform this action")

            rec.approved_by_finance = self.env.user
            rec.state = 'approved'
            rec.message_post(body=f"Mission approved by finance: {self.env.user.name}")

    def action_set_paid(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError("Only approved missions can be set as paid")

            rec.state = 'paid'
            rec.message_post(body="Mission marked as paid")

    def action_cancel(self):
        for rec in self:
            if rec.state in ['paid']:
                raise UserError("Cannot cancel already paid missions")

            rec.state = 'cancelled'
            rec.message_post(body="Mission cancelled")

    def action_reject(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Mission',
            'res_model': 'mission.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_mission_id': self.id}
        }

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ['cancelled', 'rejected']:
                raise UserError("Only cancelled or rejected missions can be reset to draft")

            rec.state = 'draft'
            rec.rejection_reason = False
            rec.message_post(body="Mission reset to draft")

    # Business logic methods
    def _get_allowance_summary(self):
        """Get summary of allowances for reporting"""
        self.ensure_one()
        summary = {}
        for line in self.allowance_line_ids:
            allowance_type = line.allowance_type
            if allowance_type not in summary:
                summary[allowance_type] = 0
            summary[allowance_type] += line.total_amount
        return summary

    def _check_user_approval_rights(self):
        """Check if current user has rights to approve this mission"""
        self.ensure_one()
        user = self.env.user
        if user.has_group('hr.group_hr_manager') and self.state == 'to_manager':
            return True
        elif user.has_group('hr.group_hr_user') and self.state == 'to_hr':
            return True
        elif user.has_group('account.group_account_user') and self.state == 'to_finance':
            return True
        return False

    # Override create and write methods for additional validation
    @api.model_create_multi
    def create(self, vals_list):
        # Prepare batch sequence generation
        # sequence_code = 'employee.mission'
        # sequence = self.env['ir.sequence'].sudo()
        #
        # # Generate sequences for all records that need one
        # sequences_to_generate = [
        #     i for i, vals in enumerate(vals_list)
        #     if not vals.get('name') or vals.get('name') == '/'
        # ]
        #
        # if sequences_to_generate:
        #     sequences = sequence.next_by_code(sequence_code, len(sequences_to_generate))
        #     for i, index in enumerate(sequences_to_generate):
        #         vals_list[index]['name'] = sequences[i] if i < len(sequences) else sequence.next_by_code(sequence_code)

        # Set managers and create records
        for vals in vals_list:
            if 'employee_id' in vals and not vals.get('manager_id'):
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                if employee.parent_id:
                    vals['manager_id'] = employee.parent_id.id

        records = super().create(vals_list)

        # Batch subscribe to messages
        partner_ids = []
        for record in records:
            if record.employee_id.user_id:
                partner_ids.append(record.employee_id.user_id.partner_id.id)

        if partner_ids:
            records.message_subscribe(partner_ids=partner_ids)

        return records

    def write(self, vals):
        if 'state' in vals and vals['state'] == 'paid':
            for rec in self:
                if rec.grand_total <= 0:
                    raise UserError("Cannot mark mission as paid with zero total amount")

        result = super().write(vals)
        return result

    # Utility methods
    def name_get(self):
        result = []
        for record in self:
            name = f"{record.name} - {record.employee_id.name}"
            result.append((record.id, name))
        return result

