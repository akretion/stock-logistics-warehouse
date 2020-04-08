# -*- coding: utf-8 -*-
# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from openerp import api, models, tools


class StockLocation(models.Model):
    _inherit = "stock.location"

    @tools.ormcache(skiparg=0)
    @api.multi
    def _location_parent_tree(self):
        self.ensure_one()
        tree = self.search([
            ('parent_right', '>=', self.parent_right),
            ('parent_left', '<=', self.parent_left)
        ], order="parent_left desc")
        return tree

    @api.model
    def create(self, vals_list):
        locations = super(StockLocation, self).create(vals_list)
        self._location_parent_tree.clear_cache(self)
        return locations

    @api.multi
    def write(self, values):
        res = super(StockLocation, self).write(values)
        self._location_parent_tree.clear_cache(self)
        return res

    @api.multi
    def unlink(self):
        res = super(StockLocation, self).unlink()
        self._location_parent_tree.clear_cache(self)
        return res
