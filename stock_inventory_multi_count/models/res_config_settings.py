# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    inventory_multi_count_max_rounds = fields.Integer(
        related="company_id.inventory_multi_count_max_rounds",
        readonly=False,
    )
    inventory_multi_count_tolerance_type = fields.Selection(
        related="company_id.inventory_multi_count_tolerance_type",
        readonly=False,
    )
    inventory_multi_count_tolerance_value = fields.Float(
        related="company_id.inventory_multi_count_tolerance_value",
        readonly=False,
    )
    inventory_multi_count_different_counter = fields.Boolean(
        related="company_id.inventory_multi_count_different_counter",
        readonly=False,
    )
    inventory_multi_count_uncounted_policy = fields.Selection(
        related="company_id.inventory_multi_count_uncounted_policy",
        readonly=False,
    )
    inventory_multi_count_first_round_criterion = fields.Selection(
        related="company_id.inventory_multi_count_first_round_criterion",
        readonly=False,
    )
    inventory_multi_count_zero_moves = fields.Boolean(
        related="company_id.inventory_multi_count_zero_moves",
        readonly=False,
    )
