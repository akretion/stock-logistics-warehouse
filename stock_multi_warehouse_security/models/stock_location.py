# -*- coding: utf-8 -*-
# Copyright (C) 2019 Akretion
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from openerp import api, fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    @api.multi
    # FIXME this depends on warehouse_id does not work in v8.
    # I put it to solve this on migration, but only location_id is taken into account
    # which can lead to some bug on warehouse computation...
    @api.depends('location_id.warehouse_id')
    def _compute_warehouse(self):
        for location in self:
            location.warehouse_id = self.get_warehouse(location)

    warehouse_id = fields.Many2one(
        'stock.warehouse', compute='_compute_warehouse',
        store=True, index=True)
