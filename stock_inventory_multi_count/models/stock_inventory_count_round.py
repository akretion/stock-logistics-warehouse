# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import split_every


class StockInventoryCountRound(models.Model):
    _name = "stock.inventory.count.round"
    _description = "Inventory Count Round"
    _inherit = ["mail.thread"]
    _order = "inventory_id, round_number"

    name = fields.Char(compute="_compute_name", store=True)
    inventory_id = fields.Many2one(
        comodel_name="stock.inventory",
        string="Inventory",
        required=True,
        ondelete="cascade",
        index=True,
    )
    round_number = fields.Integer(required=True, default=1, index=True)
    company_id = fields.Many2one(
        related="inventory_id.company_id",
        store=True,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("in_progress", "Counting"),
            ("done", "Closed"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    user_ids = fields.Many2many(
        comodel_name="res.users",
        string="Counters",
        help="Users allowed to enter the counts of this round.",
    )
    date_start = fields.Datetime(readonly=True)
    date_end = fields.Datetime(readonly=True)
    line_ids = fields.One2many(
        comodel_name="stock.inventory.count.line",
        inverse_name="round_id",
        string="Count Lines",
    )
    line_count = fields.Integer(compute="_compute_line_stats")
    counted_count = fields.Integer(compute="_compute_line_stats")
    progress = fields.Float(compute="_compute_line_stats", group_operator="avg")

    _sql_constraints = [
        (
            "inventory_round_uniq",
            "unique(inventory_id, round_number)",
            "A count round number must be unique within an inventory.",
        ),
        (
            "round_number_positive",
            "CHECK(round_number > 0)",
            "The round number must be strictly positive.",
        ),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("inventory_id.name", "round_number")
    def _compute_name(self):
        for rec in self:
            rec.name = _(
                "%(inventory)s / Count %(number)s",
                inventory=rec.inventory_id.name or "",
                number=rec.round_number,
            )

    def _compute_line_stats(self):
        """Counters via ``read_group``.

        A stored compute over the ``line_ids`` one2many would iterate every
        line of a full physical inventory each time one count is entered.
        """
        line_model = self.env["stock.inventory.count.line"]
        totals = line_model.read_group(
            [("round_id", "in", self.ids)], ["round_id"], ["round_id"]
        )
        total_by_round = {row["round_id"][0]: row["round_id_count"] for row in totals}
        counted = line_model.read_group(
            [("round_id", "in", self.ids), ("counted", "=", True)],
            ["round_id"],
            ["round_id"],
        )
        counted_by_round = {
            row["round_id"][0]: row["round_id_count"] for row in counted
        }
        for rec in self:
            total = total_by_round.get(rec.id, 0)
            done = counted_by_round.get(rec.id, 0)
            rec.line_count = total
            rec.counted_count = done
            rec.progress = (100.0 * done / total) if total else 0.0

    # ------------------------------------------------------------------
    # Line generation
    # ------------------------------------------------------------------
    def _batch_size(self):
        self.ensure_one()
        return self.company_id.stock_inventory_batch_size or 1000

    @api.model
    def _prepare_line_from_quant(self, quant):
        return {
            "quant_id": quant.id,
            "product_id": quant.product_id.id,
            "location_id": quant.location_id.id,
            "lot_id": quant.lot_id.id or False,
            "package_id": quant.package_id.id or False,
            "owner_id": quant.owner_id.id or False,
            "theoretical_qty": quant.quantity,
            "state": "pending",
        }

    def _generate_lines_from_quants(self, quants):
        """Create the lines of a first round out of the inventory quants."""
        self.ensure_one()
        line_model = self.env["stock.inventory.count.line"].sudo()
        batch = self._batch_size()
        for chunk in split_every(batch, quants.ids):
            vals_list = []
            for quant in self.env["stock.quant"].browse(list(chunk)):
                vals = self._prepare_line_from_quant(quant)
                vals["round_id"] = self.id
                vals_list.append(vals)
            if vals_list:
                line_model.create(vals_list)
        return True

    def _prepare_next_round_line(self, line):
        """Carry a divergent line over to the next round.

        The theoretical quantity is re-snapshotted here: it is the reference
        against which a stock movement during the next round is detected.
        """
        quant = line._find_quant()
        return {
            "quant_id": quant.id or False,
            "product_id": line.product_id.id,
            "location_id": line.location_id.id,
            "lot_id": line.lot_id.id or False,
            "package_id": line.package_id.id or False,
            "owner_id": line.owner_id.id or False,
            "theoretical_qty": quant.quantity if quant else 0.0,
            "previous_qty": line.counted_qty,
            "previous_user_id": line.user_id.id or False,
            "state": "pending",
        }

    def _create_next_round(self, lines):
        self.ensure_one()
        next_round = self.create(
            {
                "inventory_id": self.inventory_id.id,
                "round_number": self.round_number + 1,
            }
        )
        line_model = self.env["stock.inventory.count.line"].sudo()
        batch = self._batch_size()
        for chunk in split_every(batch, lines.ids):
            vals_list = []
            for line in lines.browse(list(chunk)):
                vals = self._prepare_next_round_line(line)
                vals["round_id"] = next_round.id
                vals_list.append(vals)
            if vals_list:
                line_model.create(vals_list)
        # The old lines are history now: they must not keep the inventory open.
        lines.write({"state": "superseded"})
        next_round.action_start()
        self.inventory_id.message_post(
            body=_(
                "Round %(number)s created with %(count)s divergent lines.",
                number=next_round.round_number,
                count=len(lines),
            )
        )
        return next_round

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_start(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(
                    _("Only a draft round can be started (%s).", rec.display_name)
                )
            rec.write({"state": "in_progress", "date_start": fields.Datetime.now()})
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        self.mapped("line_ids").filtered(lambda line: line.state != "applied").write(
            {"state": "cancel"}
        )
        return True

    def _handle_uncounted_lines(self, lines):
        """Apply the inventory policy to the lines nobody counted."""
        self.ensure_one()
        policy = self.inventory_id.uncounted_policy
        uncounted = lines.filtered(lambda line: not line.counted)
        if not uncounted:
            return lines
        if policy == "block":
            raise UserError(
                _(
                    "%(count)s lines of %(round)s have not been counted. Count "
                    "them, or change the uncounted lines policy on the "
                    "inventory.",
                    count=len(uncounted),
                    round=self.display_name,
                )
            )
        uncounted = uncounted.with_context(skip_count_checks=True)
        if policy == "zero":
            uncounted.sudo().write({"counted_qty": 0.0, "counted": True})
        else:  # theoretical
            for line in uncounted.sudo():
                line.counted_qty = line.theoretical_qty
            uncounted.sudo().write({"counted": True})
        return lines

    def _evaluate_lines(self, lines):
        """Split ``lines`` into (matched, divergent) for this round."""
        self.ensure_one()
        inventory = self.inventory_id
        line_model = lines.browse()
        first_round = self.round_number == 1
        if first_round and inventory.first_round_criterion == "none":
            # Deliberately no acceptance criterion on the first round: a single
            # count is never evidence on its own.
            return line_model, lines
        matched_ids, divergent_ids = [], []
        # ``sudo`` only to read the manager-restricted reference quantities;
        # the recordsets returned stay in the caller's environment so that the
        # stock manager check in ``_apply_inventory`` is not bypassed.
        for line in lines.sudo():
            reference = line.theoretical_qty if first_round else line.previous_qty
            if inventory._is_within_tolerance(
                line.counted_qty, reference, line.product_id
            ):
                matched_ids.append(line.id)
            else:
                divergent_ids.append(line.id)
        return line_model.browse(matched_ids), line_model.browse(divergent_ids)

    def action_close(self):
        self.ensure_one()
        if self.state != "in_progress":
            raise UserError(
                _("Only a round being counted can be closed (%s).", self.display_name)
            )
        inventory = self.inventory_id
        lines = self.line_ids.filtered(
            lambda line: line.state in ("pending", "counted")
        )
        self._handle_uncounted_lines(lines)
        matched, divergent = self._evaluate_lines(lines)

        applied, conflicts = matched._apply_to_stock()
        divergent |= conflicts
        divergent.write({"state": "divergent"})

        self.write({"state": "done", "date_end": fields.Datetime.now()})
        inventory.message_post(
            body=_(
                "Round %(number)s closed: %(applied)s lines reconciled, "
                "%(divergent)s to recount.",
                number=self.round_number,
                applied=len(applied),
                divergent=len(divergent),
            )
        )
        if not divergent:
            return inventory.action_state_to_done()
        if self.round_number >= inventory.max_rounds:
            return inventory._go_to_arbitration(divergent)
        return self._create_next_round(divergent)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_open_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock_inventory_multi_count.action_stock_inventory_count_line"
        )
        action["domain"] = [("round_id", "=", self.id)]
        action["context"] = {
            "default_round_id": self.id,
            "search_default_group_by_location": 1,
        }
        return action

    def action_print_count_sheet(self):
        return self.env.ref(
            "stock_inventory_multi_count.action_report_count_sheet"
        ).report_action(self)

    def action_open_import_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Import Counts"),
            "res_model": "stock.inventory.count.import",
            "view_mode": "form",
            "target": "new",
            "context": {"default_round_id": self.id},
        }

    def unlink(self):
        if self.filtered(lambda r: r.state == "done"):
            raise UserError(_("A closed count round cannot be deleted."))
        return super().unlink()
