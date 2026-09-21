# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models

from .constants import FIRST_ROUND_CRITERIA, TOLERANCE_TYPES, UNCOUNTED_POLICIES


class ResCompany(models.Model):
    _inherit = "res.company"

    inventory_multi_count_max_rounds = fields.Integer(
        string="Maximum Count Rounds",
        default=3,
        help="Number of count rounds before the inventory is escalated to "
        "arbitration. SAP and Oracle both cap automatic recounts; an "
        "uncapped loop never closes.",
    )
    inventory_multi_count_tolerance_type = fields.Selection(
        selection=TOLERANCE_TYPES,
        string="Default Tolerance Type",
        default="exact",
    )
    inventory_multi_count_tolerance_value = fields.Float(
        string="Default Tolerance",
        digits="Product Unit of Measure",
    )
    inventory_multi_count_different_counter = fields.Boolean(
        string="Require a Different Counter per Round",
        default=True,
        help="A recount entered by the counter who made the previous count "
        "confirms its own systematic error.",
    )
    inventory_multi_count_uncounted_policy = fields.Selection(
        selection=UNCOUNTED_POLICIES,
        string="Uncounted Lines Policy",
        default="block",
    )
    inventory_multi_count_first_round_criterion = fields.Selection(
        selection=FIRST_ROUND_CRITERIA,
        string="First Round Criterion",
        default="theoretical",
    )
    inventory_multi_count_zero_moves = fields.Boolean(
        string="Create Zero Quantity Moves",
        default=False,
        help="Create a zero quantity stock move for lines counted exactly as "
        "the theoretical quantity. The count line itself already provides "
        "the audit trail, so this is off by default.",
    )
