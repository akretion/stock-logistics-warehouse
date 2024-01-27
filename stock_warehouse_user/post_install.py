# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api


def set_default_warehouse_property(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env["res.company"].search([]):
        default_wh = env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        env["ir.property"]._set_default(
            "warehouse_id", "res.users", default_wh.id, company=company.id
        )
