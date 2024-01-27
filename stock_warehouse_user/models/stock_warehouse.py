from odoo import api, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        for company in warehouses.company_id:
            default_wh = self.env["stock.warehouse"].search(
                [("company_id", "=", company.id)], limit=1
            )
            self.env["ir.property"].sudo()._set_default(
                "warehouse_id", "res.users", default_wh.id, company=company.id
            )
        return warehouses
