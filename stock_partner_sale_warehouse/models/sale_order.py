# Copyright (C) 2023 Syera BONNEAUX
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.onchange('partner_shipping_id')
    def _onchange_partner_shipping_warehouse_id(self):
        warehouse = self.partner_shipping_id.default_resupply_warehouse_id
        if warehouse:
            self.warehouse_id = warehouse.id
        else:
            self.warehouse_id = self.user_id.with_company(self.company_id.id)._get_default_warehouse_id().id

    @api.onchange('user_id')
    def onchange_user_id(self):
        super().onchange_user_id()
        self._onchange_partner_shipping_warehouse_id()