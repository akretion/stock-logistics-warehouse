# coding: utf-8
# © 2017 David BEAL @ Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp import fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    picking_location_id = fields.Many2one(
        comodel_name='stock.location', string="Picking Location",
        help="In overstock locations, you can define the place where "
             "picking products are available.")
