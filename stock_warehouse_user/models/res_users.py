from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Default Warehouse",
        company_dependent=True,
        domain="[('company_id', '=', current_company_id), ('company_id', 'in', company_ids)]",
    )
