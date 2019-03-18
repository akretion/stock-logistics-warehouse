# -*- coding: utf-8 -*-
# Copyright (C) 2019 Akretion
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from openerp import api, fields, models, exceptions


class ResUsers(models.Model):
    _inherit = "res.users"

    warehouse_id = fields.Many2one(
        'stock.warehouse', required=True,
        context={'user_preference': True})
    warehouse_ids = fields.Many2many(
        'stock.warehouse',
        hel='Allowed warehouses')

    @api.model
    def _get_available_warehouse_ids(self):
        whs = super(ResUsers, self)._get_available_warehouse_ids()
        remote_whs = whs.mapped('remote_warehouse_ids')
        return whs | remote_whs

    @api.multi
    @api.constrains('warehouse_id', 'warehouse_ids')
    def _check_warehouse(self):
        if any(user.company_ids and 
               user.company_id not in user.company_ids for user in self):
            raise exceptions.Warning(
                _('The chosen warehouse is not in the allowed warehouses for \
                   this user'))
