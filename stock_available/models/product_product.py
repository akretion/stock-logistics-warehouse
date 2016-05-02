# -*- coding: utf-8 -*-
##############################################################################
#
#    This module is copyright (C) 2014 Numérigraphe SARL. All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api
from openerp.addons import decimal_precision as dp


class ProductProduct(models.Model):
    """Add a field for the stock available to promise.
    Useful implementations need to be installed through the Settings menu or by
    installing one of the modules stock_available_*
    """
    _inherit = 'product.product'

    @api.one
    @api.depends('virtual_available')
    def _immediately_usable_qty(self):
        """No-op implementation of the stock available to promise.

        By default, available to promise = forecasted quantity.

        Must be overridden by another module that actually implement
        computations."""
        self.immediately_usable_qty = self.virtual_available

    def _search_immediately_usable_quantity(self, operator, value):
        res = []
        assert operator in (
            '<', '>', '=', '!=', '<=', '>='
        ), 'Invalid domain operator'
        assert isinstance(
            value, (float, int)
        ), 'Invalid domain value'
        if operator == '=':
            operator = '=='

        ids = []
        products = self.search([])
        for prod in products:
            if eval(str(prod.immediately_usable_qty) + operator + str(value)):
                ids.append(prod.id)
        res.append(('id', 'in', ids))
        return res

    immediately_usable_qty = fields.Float(
        digits=dp.get_precision('Product Unit of Measure'),
        compute='_immediately_usable_qty',
        search='_search_immediately_usable_quantity',
        string='Available to promise',
        help="Stock for this Product that can be safely proposed "
             "for sale to Customers.\n"
             "The definition of this value can be configured to suit "
             "your needs")
