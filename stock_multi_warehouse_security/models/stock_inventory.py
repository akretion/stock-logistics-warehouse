# -*- coding: utf-8 -*-
# Copyright (C) 2019 Akretion
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from openerp import api, fields, models


class StockInventory(models.Model):
    _inherit = "stock.inventory"

    warehouse_id = fields.Many2one(
        'stock.warehouse', related='location_id.warehouse_id',
        store=True, index=True, readonly=True)
