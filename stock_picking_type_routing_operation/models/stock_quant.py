# Copyright 2019 Camptocamp (https://www.camptocamp.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
"""Allow forcing reservations of quants in a location (or children)

When the context key "force_reservation_location_id" is passed, it will look
in this location or its children.

Example::

    moves.with_context(
        gather_in_location_id=location.id,
    ).action_assign()

"""

from openerp import api, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def quants_get_prefered_domain(self, location, product, qty, domain=None,
                                   prefered_domain_list=[],
                                   restrict_lot_id=False,
                                   restrict_partner_id=False):
        reservation_location_id = self.env.context.get(
            'gather_in_location_id')
        if reservation_location_id:
            location = self.env['stock.location'].browse(
                reservation_location_id)
        return super(StockQuant, self).quants_get_prefered_domain(
            location, product, qty, domain=domain,
            prefered_domain_list=prefered_domain_list,
            restrict_lot_id=restrict_lot_id,
            restrict_partner_id=restrict_partner_id)
