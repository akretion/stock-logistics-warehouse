# -*- coding: utf-8 -*-
# Copyright (C) 2019 Akretion
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from openerp import api, models
from ast import literal_eval


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.multi
    def action_view_orderpoints(self):
        res = super(ProductTemplate, self).action_view_orderpoints()
        # in v12, the context is already a dict and not a str, so we can 
        # skip this part and just add the warehouse as we would update a
        # normal dict
        context = literal_eval(res['context'] or {})
        context.update({
            'search_default_warehouse_id': self.env.user.warehouse_id.id
        })
        res['context'] = str(context)
        return res

    @api.multi
    def action_open_quants(self):
        res = super(ProductTemplate, self).action_open_quants()
        # in v12, the context is already a dict and not a str, so we can 
        # skip this part and just add the warehouse as we would update a
        # normal dict
        context = literal_eval(res['context'] or {})
        context.update({
            'search_default_warehouse_id': self.env.user.warehouse_id.id
        })
        res['context'] = str(context)
        return res

    @api.multi
    def action_view_stock_moves(self):
        res = super(ProductTemplate, self).action_view_stock_moves()
        # in v12, the context is already a dict and not a str, so we can 
        # skip this part and just add the warehouse as we would update a
        # normal dict
        context = literal_eval(res['context'] or {})
        context.update({
            'search_default_warehouse_id': self.env.user.warehouse_id.id
        })
        res['context'] = str(context)
        return res

