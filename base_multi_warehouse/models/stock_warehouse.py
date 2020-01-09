# -*- coding: utf-8 -*-
# Copyright (C) 2019 Akretion
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from openerp import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    user_ids = fields.One2many(
        'res.users',
        'warehouse_id',
        string="Users"
    )
