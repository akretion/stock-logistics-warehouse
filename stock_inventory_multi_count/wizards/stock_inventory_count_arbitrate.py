# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

MANAGER_GROUP = "stock.group_stock_manager"


class StockInventoryCountArbitrate(models.TransientModel):
    _name = "stock.inventory.count.arbitrate"
    _description = "Arbitrate Divergent Count Lines"

    line_ids = fields.Many2many(
        comodel_name="stock.inventory.count.line",
        string="Lines",
        required=True,
    )
    line_count = fields.Integer(compute="_compute_line_count")
    resolution = fields.Selection(
        selection=[
            ("counted", "Accept the last count"),
            ("previous", "Accept the previous count"),
            ("theoretical", "Keep the system quantity"),
            ("manual", "Enter a supervised quantity"),
        ],
        default="counted",
        required=True,
    )
    manual_qty = fields.Float(
        string="Supervised Quantity",
        digits="Product Unit of Measure",
    )
    note = fields.Text(
        string="Justification",
        required=True,
        help="Recorded on every arbitrated line. Arbitration overrides two "
        "independent physical counts, so it must be explained.",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for wiz in self:
            wiz.line_count = len(wiz.line_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") == "stock.inventory.count.line":
            res["line_ids"] = [(6, 0, self.env.context.get("active_ids", []))]
        return res

    def _check_access(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(_("Only a stock manager can arbitrate a divergent count."))

    def _final_qty_for(self, line):
        self.ensure_one()
        if self.resolution == "counted":
            return line.counted_qty
        if self.resolution == "previous":
            return line.previous_qty
        if self.resolution == "theoretical":
            return line.theoretical_qty
        return self.manual_qty

    def action_confirm(self):
        self.ensure_one()
        self._check_access()
        if self.resolution == "manual" and len(self.line_ids) > 1:
            raise UserError(
                _(
                    "A supervised quantity can only be entered for one line at "
                    "a time."
                )
            )
        lines = self.line_ids.filtered(
            lambda line: line.state in ("divergent", "counted", "pending")
        )
        if not lines:
            raise UserError(_("None of the selected lines can be arbitrated."))
        inventories = lines.mapped("inventory_id")
        if len(inventories) > 1:
            raise UserError(_("Select lines from a single inventory at a time."))
        for line in lines.sudo():
            line.write(
                {
                    "arbitration_qty": self._final_qty_for(line),
                    "arbitrated_by_id": self.env.user.id,
                    "note": self.note,
                    "state": "arbitrated",
                }
            )
        applied, conflicts = lines._apply_to_stock()
        if conflicts:
            conflicts.write({"state": "divergent"})
            raise UserError(
                _(
                    "%(count)s lines could not be applied because the stock "
                    "moved during the count. Recount them.",
                    count=len(conflicts),
                )
            )
        inventories.message_post(
            body=_(
                "%(count)s lines arbitrated by %(user)s: %(note)s",
                count=len(applied),
                user=self.env.user.display_name,
                note=self.note,
            )
        )
        remaining = inventories.count_line_ids.filtered(
            lambda line: line.state in ("pending", "counted", "divergent")
        )
        # ``superseded`` lines are history and never block the closing.
        open_rounds = inventories.round_ids.filtered(
            lambda r: r.state in ("draft", "in_progress")
        )
        if not remaining and not open_rounds:
            inventories.action_state_to_done()
        return {"type": "ir.actions.act_window_close"}
