from odoo import fields, models, api
from odoo.exceptions import ValidationError


class HrMissionType(models.Model):
    _name = 'hr.mission.type'
    _description = 'Mission Type'
    _order = 'name'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    # Basic Information
    name = fields.Char(string='Mission Type Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, copy=False)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Description', translate=True)
    color = fields.Integer(string='Color Index')

    # Approval Settings
    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=True,
        help="If checked, this mission type will require approval workflow"
    )
    approval_level = fields.Selection([
        ('manager', 'Manager Only'),
        ('hr', 'Manager + HR'),
        ('full', 'Full Approval Chain')
    ], string='Approval Level', default='full',
        help="Define the approval chain required for this mission type")

    # Duration Settings
    max_duration = fields.Integer(
        string='Maximum Duration (Days)',
        help="Maximum allowed duration for this mission type. Leave 0 for no limit"
    )
    min_duration = fields.Float(
        string='Minimum Duration (Hours)',
        help="Minimum duration required for this mission type"
    )

    # Allowance Settings
    apply_allowance = fields.Boolean(
        string='Apply Daily Allowance',
        default=False,
        help="Enable daily allowance calculation for this mission type"
    )
    daily_allowance = fields.Monetary(
        string='Daily Allowance Amount',
        currency_field='currency_id',
        help="Daily allowance amount for this mission type"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Time Off Integration
    create_time_off = fields.Boolean(
        string='Create Time Off',
        default=True,
        help="Automatically create a time off record when mission is approved by HR"
    )
    time_off_type_id = fields.Many2one(
        'hr.leave.type',
        string='Related Time Off Type',
        domain="[('allocation_type', '=', 'no'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Time off type to use when creating leave for this mission type"
    )
    time_off_required = fields.Boolean(
        string='Time Off Required',
        default=False,
        help="If checked, time off type must be configured"
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    # Statistics (computed fields)
    mission_count = fields.Integer(
        string='Mission Count',
        compute='_compute_mission_count'
    )

    # SQL Constraints
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code, company_id)',
         'Mission type code must be unique per company!'),
        ('daily_allowance_positive', 'CHECK(daily_allowance >= 0)',
         'Daily allowance must be positive!'),
        ('max_duration_positive', 'CHECK(max_duration >= 0)',
         'Maximum duration must be positive!'),
    ]

    # Python Constraints
    @api.constrains('max_duration', 'min_duration')
    def _check_duration_limits(self):
        """Validate duration limits"""
        for rec in self:
            if rec.max_duration > 0 and rec.min_duration > 0:
                # Convert max_duration (days) to hours for comparison
                max_hours = rec.max_duration * 24
                if rec.min_duration > max_hours:
                    raise ValidationError(
                        f"Minimum duration ({rec.min_duration} hours) cannot be greater than "
                        f"maximum duration ({rec.max_duration} days = {max_hours} hours)"
                    )

    @api.constrains('time_off_required', 'time_off_type_id', 'create_time_off')
    def _check_time_off_configuration(self):
        """Validate time off configuration"""
        for rec in self:
            if rec.time_off_required and not rec.time_off_type_id:
                raise ValidationError(
                    f"Time Off Type is required for mission type '{rec.name}' "
                    f"because 'Time Off Required' is checked."
                )
            if rec.time_off_type_id and not rec.create_time_off:
                raise ValidationError(
                    f"Cannot set Time Off Type without enabling 'Create Time Off' "
                    f"for mission type '{rec.name}'"
                )

    @api.constrains('apply_allowance', 'daily_allowance')
    def _check_allowance_configuration(self):
        """Validate allowance configuration"""
        for rec in self:
            if rec.apply_allowance and rec.daily_allowance <= 0:
                raise ValidationError(
                    f"Daily allowance must be greater than 0 when 'Apply Allowance' "
                    f"is enabled for mission type '{rec.name}'"
                )

    # Onchange Methods
    @api.onchange('apply_allowance')
    def _onchange_apply_allowance(self):
        """Clear daily allowance when apply_allowance is disabled"""
        if not self.apply_allowance:
            self.daily_allowance = 0.0

    @api.onchange('create_time_off')
    def _onchange_create_time_off(self):
        """Clear time off type when create_time_off is disabled"""
        if not self.create_time_off:
            self.time_off_type_id = False
            self.time_off_required = False

    @api.onchange('time_off_type_id')
    def _onchange_time_off_type_id(self):
        """Auto-enable create_time_off when time_off_type is set"""
        if self.time_off_type_id and not self.create_time_off:
            self.create_time_off = True

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Update currency when company changes"""
        if self.company_id:
            self.currency_id = self.company_id.currency_id

    # Compute Methods
    def _compute_mission_count(self):
        """Compute number of missions using this type"""
        for rec in self:
            rec.mission_count = self.env['hr.mission'].search_count([
                ('type_id', '=', rec.id)
            ])

    # Action Methods
    def action_view_missions(self):
        """Smart button to view missions of this type"""
        self.ensure_one()
        return {
            'name': f'Missions - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.mission',
            'view_mode': 'list,form',
            'domain': [('type_id', '=', self.id)],
            'context': {'default_type_id': self.id}
        }

    # CRUD Overrides
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure code is uppercase"""
        for vals in vals_list:
            if vals.get('code'):
                vals['code'] = vals['code'].upper()
        return super().create(vals_list)

    def write(self, vals):
        """Override write to ensure code is uppercase"""
        if vals.get('code'):
            vals['code'] = vals['code'].upper()
        return super().write(vals)

    # Utility Methods
    def name_get(self):
        """Custom name display with code"""
        result = []
        for record in self:
            if record.code:
                name = f"[{record.code}] {record.name}"
            else:
                name = record.name
            result.append((record.id, name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """Search by name or code"""
        args = args or []
        if name:
            domain = ['|', ('name', operator, name), ('code', operator, name)]
            return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
        return super()._name_search(name, args, operator, limit, name_get_uid)

    def copy(self, default=None):
        """Override copy to modify name and code"""
        default = dict(default or {})
        if not default.get('name'):
            default['name'] = f"{self.name} (Copy)"
        if not default.get('code'):
            default['code'] = f"{self.code}_COPY"
        return super().copy(default)
