# -*- coding: utf-8 -*-
# Copyright 2020 Camptocamp (https://www.camptocamp.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from openerp import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    canceled_by_routing = fields.Boolean(
        default=False,
        help="Technical field. Indicates the transfer is"
        " canceled because it was left empty after a routing operation.",
    )

    @api.multi
    def _routing_operation_handle_empty(self):
        """Handle pickings emptied during a routing operation"""
        for picking in self:
            if not picking.move_lines:
                # we skip the canceled part in v8
                picking.canceled_by_routing = True
