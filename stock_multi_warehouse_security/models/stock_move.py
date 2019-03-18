# -*- coding: utf-8 -*-
# Copyright (C) 2019 Akretion
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from openerp import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    # Only add index
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        'Warehouse',
        index=True,
        help="Technical field depicting the warehouse to consider for the \
              route selection on the next procurement (if any).")

    @api.model
    def _get_move_default_warehouse(self, vals):
        if vals.get('picking_type_id'):
            pick_type = self.env['stock.picking.type'].browse(
                vals['picking_type_id'])
            wh = pick_type.warehouse_id
        else:
            locations = self.env['stock.location'].browse(
                [vals['location_id'], vals['location_dest_id']])
            whs = locations.mapped('warehouse_id')
            wh = len(whs) <=1 and whs or self.env['stock.warehouse']
        return wh

    @api.model
    def create(self, vals):
        if not vals.get('warehouse_id'):
            wh = self._get_move_default_warehouse(vals)
            vals['warehouse_id'] = wh.id or False
        return super(StockMove, self).create(vals)
