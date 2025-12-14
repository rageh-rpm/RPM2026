# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Simple flag instead of new type
    is_overdraft_facility = fields.Boolean(
        string='Is Overdraft Facility',
        help='Check this if this bank account has overdraft facility'
    )

    overdraft_facility_ids = fields.One2many(
        'overdraft.facility',
        'journal_id',
        string='Overdraft Facilities'
    )

    active_facility_id = fields.Many2one(
        'overdraft.facility',
        string='Active Facility',
        compute='_compute_active_facility',
        store=True
    )

    facility_count = fields.Integer(
        string='Facilities Count',
        compute='_compute_facility_count'
    )

    @api.depends('overdraft_facility_ids.state', 'overdraft_facility_ids.date_from', 'overdraft_facility_ids.date_to')
    def _compute_active_facility(self):
        today = fields.Date.today()
        for journal in self:
            facility = journal.overdraft_facility_ids.filtered(
                lambda f: f.state == 'active' and f.date_from <= today <= f.date_to
            )
            journal.active_facility_id = facility[:1] if facility else False

    @api.depends('overdraft_facility_ids')
    def _compute_facility_count(self):
        for journal in self:
            journal.facility_count = len(journal.overdraft_facility_ids)

    def action_view_facilities(self):
        self.ensure_one()
        return {
            'name': 'Overdraft Facilities',
            'type': 'ir.actions.act_window',
            'res_model': 'overdraft.facility',
            'view_mode': 'list,form',
            'domain': [('journal_id', '=', self.id)],
            'context': {'default_journal_id': self.id}
        }
