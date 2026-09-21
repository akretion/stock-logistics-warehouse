# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

from .constants import FIRST_ROUND_CRITERIA, TOLERANCE_TYPES, UNCOUNTED_POLICIES

READONLY_STATES = {"draft": [("readonly", False)]}


class StockInventory(models.Model):
    _inherit = "stock.inventory"

    state = fields.Selection(
        selection_add=[("arbitration", "Arbitration"), ("done",)],
        ondelete={"arbitration": "set default"},
    )
    count_mode = fields.Selection(
        selection=[
            ("single", "Single count"),
            ("multi", "Blind multi count"),
        ],
        default="single",
        required=True,
        readonly=True,
        states=READONLY_STATES,
        help="Blind multi count hides the theoretical quantity from the "
        "counters and recounts only the divergent lines, round after round.",
    )
    blind_count = fields.Boolean(
        default=True,
        readonly=True,
        states=READONLY_STATES,
        help="Technical flag kept for reporting. The theoretical quantity is "
        "restricted to stock managers at ORM level regardless of this flag.",
    )
    max_rounds = fields.Integer(
        string="Maximum Rounds",
        readonly=True,
        states=READONLY_STATES,
        default=lambda self: self.env.company.inventory_multi_count_max_rounds,
    )
    require_different_counter = fields.Boolean(
        readonly=True,
        states=READONLY_STATES,
        default=lambda self: self.env.company.inventory_multi_count_different_counter,
    )
    first_round_criterion = fields.Selection(
        selection=FIRST_ROUND_CRITERIA,
        readonly=True,
        states=READONLY_STATES,
        default=lambda self: (
            self.env.company.inventory_multi_count_first_round_criterion
        ),
    )
    tolerance_type = fields.Selection(
        selection=TOLERANCE_TYPES,
        readonly=True,
        states=READONLY_STATES,
        default=lambda self: self.env.company.inventory_multi_count_tolerance_type,
    )
    tolerance_value = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        states=READONLY_STATES,
        default=lambda self: self.env.company.inventory_multi_count_tolerance_value,
    )
    uncounted_policy = fields.Selection(
        selection=UNCOUNTED_POLICIES,
        readonly=True,
        states=READONLY_STATES,
        default=lambda self: (self.env.company.inventory_multi_count_uncounted_policy),
    )
    create_zero_moves = fields.Boolean(
        readonly=True,
        states=READONLY_STATES,
        default=lambda self: self.env.company.inventory_multi_count_zero_moves,
    )
    round_ids = fields.One2many(
        comodel_name="stock.inventory.count.round",
        inverse_name="inventory_id",
        string="Count Rounds",
    )
    count_line_ids = fields.One2many(
        comodel_name="stock.inventory.count.line",
        inverse_name="inventory_id",
        string="Count Lines",
    )
    current_round_id = fields.Many2one(
        comodel_name="stock.inventory.count.round",
        compute="_compute_current_round_id",
        string="Current Round",
    )
    current_round_number = fields.Integer(
        compute="_compute_current_round_id",
    )
    round_count = fields.Integer(compute="_compute_round_count")
    count_line_count = fields.Integer(compute="_compute_round_count")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("round_ids.state", "round_ids.round_number")
    def _compute_current_round_id(self):
        for rec in self:
            rounds = rec.round_ids.filtered(
                lambda r: r.state in ("draft", "in_progress")
            ).sorted("round_number")
            current = rounds[:1]
            rec.current_round_id = current
            rec.current_round_number = current.round_number or 0

    def _compute_round_count(self):
        round_data = self.env["stock.inventory.count.round"].read_group(
            [("inventory_id", "in", self.ids)], ["inventory_id"], ["inventory_id"]
        )
        rounds_by_inv = {
            row["inventory_id"][0]: row["inventory_id_count"] for row in round_data
        }
        line_data = self.env["stock.inventory.count.line"].read_group(
            [("inventory_id", "in", self.ids)], ["inventory_id"], ["inventory_id"]
        )
        lines_by_inv = {
            row["inventory_id"][0]: row["inventory_id_count"] for row in line_data
        }
        for rec in self:
            rec.round_count = rounds_by_inv.get(rec.id, 0)
            rec.count_line_count = lines_by_inv.get(rec.id, 0)

    def _compute_action_state_to_cancel_allowed(self):
        """A physical inventory that goes wrong must be cancellable.

        The base module only allows cancelling a draft adjustment, which would
        leave a multi count stuck with its quants flagged ``to_do``.
        """
        res = super()._compute_action_state_to_cancel_allowed()
        for rec in self:
            if rec.count_mode == "multi" and rec.state in (
                "in_progress",
                "arbitration",
            ):
                rec.action_state_to_cancel_allowed = True
        return res

    # ------------------------------------------------------------------
    # Tolerance
    # ------------------------------------------------------------------
    def _tolerance_value_for(self, product):
        """Hook: return the tolerance to use for ``product``.

        Override to read the tolerance from the product, its category or the
        location (e.g. to glue this module to ``stock_inventory_discrepancy``).
        """
        self.ensure_one()
        return self.tolerance_value

    def _is_within_tolerance(self, counted_qty, reference_qty, product):
        """Return True when ``counted_qty`` is close enough to ``reference_qty``."""
        self.ensure_one()
        rounding = product.uom_id.rounding
        diff = counted_qty - reference_qty
        if float_is_zero(diff, precision_rounding=rounding):
            return True
        tolerance = self._tolerance_value_for(product)
        if self.tolerance_type == "exact" or not tolerance:
            return False
        if self.tolerance_type == "qty":
            return float_compare(abs(diff), tolerance, precision_rounding=rounding) <= 0
        if self.tolerance_type == "percent":
            if float_is_zero(reference_qty, precision_rounding=rounding):
                # No basis for a percentage: any deviation from zero is a
                # divergence. This is deliberate -- stock appearing in a
                # location the system believes empty always deserves a recount.
                return False
            return abs(100.0 * diff / reference_qty) <= tolerance
        if self.tolerance_type == "value":
            price = product.with_company(self.company_id).standard_price
            return abs(diff) * price <= tolerance
        return False

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def action_state_to_in_progress(self):
        res = super().action_state_to_in_progress()
        for rec in self.filtered(lambda i: i.count_mode == "multi"):
            if rec.max_rounds < 1:
                raise UserError(_("The maximum number of rounds must be at least 1."))
            rec._create_first_round()
        return res

    def _create_first_round(self):
        self.ensure_one()
        if self.round_ids:
            raise UserError(
                _("Count rounds already exist for %(name)s.", name=self.display_name)
            )
        count_round = self.env["stock.inventory.count.round"].create(
            {
                "inventory_id": self.id,
                "round_number": 1,
                "user_ids": [(6, 0, self.responsible_id.ids)],
            }
        )
        count_round._generate_lines_from_quants(self.stock_quant_ids)
        count_round.action_start()
        return count_round

    def action_state_to_done(self):
        for rec in self.filtered(lambda i: i.count_mode == "multi"):
            open_rounds = rec.round_ids.filtered(
                lambda r: r.state in ("draft", "in_progress")
            )
            if open_rounds and not self.env.context.get("force_inventory_done"):
                raise UserError(
                    _(
                        "Round %(round)s is still open. Close it before setting "
                        "the inventory to done.",
                        round=", ".join(open_rounds.mapped("display_name")),
                    )
                )
            pending = rec.count_line_ids.filtered(
                lambda line: line.state in ("pending", "counted", "divergent")
            )
            if pending and not self.env.context.get("force_inventory_done"):
                raise UserError(
                    _(
                        "%(count)s count lines are still unresolved. Arbitrate "
                        "them before closing the inventory.",
                        count=len(pending),
                    )
                )
        return super().action_state_to_done()

    def action_auto_state_to_done(self):
        """Never auto-close a multi count.

        ``stock_inventory`` closes the adjustment as soon as no quant is left
        flagged ``to_do``. That happens in the middle of closing a round, while
        the next one still has to be counted.
        """
        self.ensure_one()
        if self.count_mode == "multi" and not self.env.context.get(
            "force_inventory_done"
        ):
            return True
        return super().action_auto_state_to_done()

    def action_state_to_draft(self):
        for rec in self.filtered(lambda i: i.count_mode == "multi"):
            if rec.count_line_ids.filtered(lambda line: line.state == "applied"):
                raise UserError(
                    _(
                        "Stock has already been adjusted by this inventory, it "
                        "cannot go back to draft."
                    )
                )
            rec.count_line_ids.unlink()
            rec.round_ids.unlink()
        return super().action_state_to_draft()

    def action_state_to_cancel(self):
        multi = self.filtered(lambda i: i.count_mode == "multi")
        res = super().action_state_to_cancel()
        for rec in multi:
            rec.round_ids.filtered(lambda r: r.state != "done").write(
                {"state": "cancel"}
            )
            rec.count_line_ids.filtered(lambda line: line.state != "applied").write(
                {"state": "cancel"}
            )
            rec._release_quants()
        return res

    def _release_quants(self):
        """Give the quants back: clear the ``to_do`` flag set when starting."""
        self.ensure_one()
        quants = self.stock_quant_ids.filtered(
            lambda q: q.current_inventory_id.id == self.id
        )
        if quants:
            quants.write(
                {
                    "to_do": False,
                    "user_id": False,
                    "inventory_date": False,
                    "current_inventory_id": False,
                }
            )

    def action_close_current_round(self):
        self.ensure_one()
        if not self.current_round_id:
            raise UserError(_("There is no open round to close."))
        return self.current_round_id.action_close()

    # ------------------------------------------------------------------
    # Arbitration
    # ------------------------------------------------------------------
    def _go_to_arbitration(self, lines):
        self.ensure_one()
        lines.write({"state": "divergent"})
        self.write({"state": "arbitration"})
        self.message_post(
            body=_(
                "Maximum number of rounds (%(max)s) reached with %(count)s "
                "unresolved lines. Arbitration required.",
                max=self.max_rounds,
                count=len(lines),
            )
        )
        return self.action_open_arbitration()

    def action_open_arbitration(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock_inventory_multi_count.action_stock_inventory_count_line"
        )
        action["name"] = _("Lines to Arbitrate")
        action["domain"] = [
            ("inventory_id", "=", self.id),
            ("state", "=", "divergent"),
        ]
        action["context"] = {"search_default_group_by_location": 1}
        return action

    def action_view_count_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock_inventory_multi_count.action_stock_inventory_count_line"
        )
        action["domain"] = [("inventory_id", "=", self.id)]
        action["context"] = {"search_default_group_by_round": 1}
        return action

    def action_view_rounds(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock_inventory_multi_count.action_stock_inventory_count_round"
        )
        action["domain"] = [("inventory_id", "=", self.id)]
        action["context"] = {"default_inventory_id": self.id}
        return action
