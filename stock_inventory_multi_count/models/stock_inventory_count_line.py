# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero, split_every
from odoo.tools.sql import create_unique_index

MANAGER_GROUP = "stock.group_stock_manager"


class StockInventoryCountLine(models.Model):
    _name = "stock.inventory.count.line"
    _description = "Inventory Count Line"
    _order = "location_id, product_id, id"
    _check_company_auto = True

    round_id = fields.Many2one(
        comodel_name="stock.inventory.count.round",
        string="Count Round",
        required=True,
        ondelete="cascade",
        index=True,
    )
    inventory_id = fields.Many2one(
        related="round_id.inventory_id",
        store=True,
        index=True,
    )
    round_number = fields.Integer(
        related="round_id.round_number",
        store=True,
    )
    round_state = fields.Selection(
        related="round_id.state",
        string="Round Status",
    )
    company_id = fields.Many2one(
        related="round_id.company_id",
        store=True,
        index=True,
    )
    quant_id = fields.Many2one(
        comodel_name="stock.quant",
        string="Quant",
        ondelete="set null",
        help="Left empty for stock found where the system expected none.",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
        index=True,
        domain="[('type', '=', 'product')]",
        check_company=True,
    )
    product_uom_id = fields.Many2one(
        related="product_id.uom_id",
        string="UoM",
    )
    product_tracking = fields.Selection(related="product_id.tracking")
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Location",
        required=True,
        index=True,
        domain="[('usage', 'in', ['internal', 'transit'])]",
        check_company=True,
    )
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lot/Serial Number",
        check_company=True,
    )
    package_id = fields.Many2one(
        comodel_name="stock.quant.package",
        string="Package",
    )
    owner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Owner",
    )

    # --- Restricted at ORM level: this is what makes the count blind. ---
    theoretical_qty = fields.Float(
        string="Theoretical Quantity",
        digits="Product Unit of Measure",
        readonly=True,
        groups=MANAGER_GROUP,
        help="On hand quantity frozen when this round was created.",
    )
    previous_qty = fields.Float(
        string="Previous Count",
        digits="Product Unit of Measure",
        readonly=True,
        groups=MANAGER_GROUP,
    )
    difference = fields.Float(
        string="Difference vs Theoretical",
        digits="Product Unit of Measure",
        compute="_compute_differences",
        store=True,
        groups=MANAGER_GROUP,
    )
    difference_percent = fields.Float(
        string="Difference (%)",
        digits=(3, 2),
        compute="_compute_differences",
        store=True,
        group_operator="avg",
        groups=MANAGER_GROUP,
    )
    difference_previous = fields.Float(
        string="Difference vs Previous Count",
        digits="Product Unit of Measure",
        compute="_compute_differences",
        store=True,
        groups=MANAGER_GROUP,
    )
    # -------------------------------------------------------------------

    counted_qty = fields.Float(
        string="Counted Quantity",
        digits="Product Unit of Measure",
    )
    counted = fields.Boolean(
        default=False,
        readonly=True,
        help="Distinguishes a line counted as zero from a line nobody counted.",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Counted By",
        readonly=True,
    )
    previous_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Previous Counter",
        readonly=True,
    )
    count_date = fields.Datetime(readonly=True)
    state = fields.Selection(
        selection=[
            ("pending", "To Count"),
            ("counted", "Counted"),
            ("matched", "Reconciled"),
            ("divergent", "Divergent"),
            ("superseded", "Recounted"),
            ("arbitrated", "Arbitrated"),
            ("applied", "Applied"),
            ("cancel", "Cancelled"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    arbitration_qty = fields.Float(
        string="Arbitrated Quantity",
        digits="Product Unit of Measure",
        readonly=True,
    )
    arbitrated_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Arbitrated By",
        readonly=True,
    )
    final_qty = fields.Float(
        string="Final Quantity",
        digits="Product Unit of Measure",
        compute="_compute_final_qty",
        store=True,
    )
    note = fields.Text(string="Justification")

    _sql_constraints = [
        (
            "counted_qty_positive",
            "CHECK(counted_qty >= 0)",
            "A counted quantity cannot be negative.",
        ),
    ]

    def init(self):
        # NULL values never collide in a plain unique constraint, so a line
        # without lot/package/owner would be duplicable. COALESCE fixes that.
        create_unique_index(
            self._cr,
            "stock_inventory_count_line_key_uniq",
            self._table,
            [
                "round_id",
                "product_id",
                "location_id",
                "COALESCE(lot_id, 0)",
                "COALESCE(package_id, 0)",
                "COALESCE(owner_id, 0)",
            ],
        )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("counted_qty", "theoretical_qty", "previous_qty")
    def _compute_differences(self):
        for line in self:
            rounding = line.product_id.uom_id.rounding or 0.01
            line.difference = line.counted_qty - line.theoretical_qty
            line.difference_previous = line.counted_qty - line.previous_qty
            if float_is_zero(line.theoretical_qty, precision_rounding=rounding):
                line.difference_percent = 0.0
            else:
                line.difference_percent = abs(
                    100.0 * line.difference / line.theoretical_qty
                )

    @api.depends("counted_qty", "arbitration_qty", "state")
    def _compute_final_qty(self):
        for line in self:
            if line.state == "arbitrated":
                line.final_qty = line.arbitration_qty
            else:
                line.final_qty = line.counted_qty

    def name_get(self):
        result = []
        for line in self:
            name = "%s - %s" % (
                line.location_id.display_name,
                line.product_id.display_name,
            )
            if line.lot_id:
                name = "%s (%s)" % (name, line.lot_id.name)
            result.append((line.id, name))
        return result

    # ------------------------------------------------------------------
    # Count entry
    # ------------------------------------------------------------------
    def _check_count_entry(self):
        """Guard rails applied when a count is entered."""
        is_manager = self.env.user.has_group(MANAGER_GROUP)
        for line in self:
            if line.round_id.state != "in_progress":
                raise UserError(
                    _(
                        "Round %(round)s is not open for counting.",
                        round=line.round_id.display_name,
                    )
                )
            if line.state in ("matched", "applied", "cancel", "superseded"):
                raise UserError(
                    _(
                        "Line %(line)s is already settled and cannot be "
                        "counted again.",
                        line=line.display_name,
                    )
                )
            counters = line.round_id.user_ids
            if counters and self.env.user not in counters and not is_manager:
                raise UserError(
                    _(
                        "You are not assigned to round %(round)s.",
                        round=line.round_id.display_name,
                    )
                )
            if (
                line.inventory_id.require_different_counter
                and line.previous_user_id
                and line.previous_user_id == self.env.user
            ):
                raise UserError(
                    _(
                        "You already counted %(line)s in the previous round. A "
                        "recount must be entered by a different person.",
                        line=line.display_name,
                    )
                )

    def write(self, vals):
        entering_count = "counted_qty" in vals and not self.env.context.get(
            "skip_count_checks"
        )
        if entering_count:
            self._check_count_entry()
            vals = dict(vals)
            vals.setdefault("counted", True)
            vals.setdefault("user_id", self.env.user.id)
            vals.setdefault("count_date", fields.Datetime.now())
        res = super().write(vals)
        if entering_count:
            pending = self.filtered(lambda line: line.state == "pending")
            if pending:
                super(StockInventoryCountLine, pending).write({"state": "counted"})
        return res

    def action_set_counted(self):
        """Confirm a line counted with the value already on screen (incl. 0)."""
        for line in self:
            line.counted_qty = line.counted_qty
        return True

    # ------------------------------------------------------------------
    # Quant resolution
    # ------------------------------------------------------------------
    def _quant_domain(self):
        self.ensure_one()
        return [
            ("product_id", "=", self.product_id.id),
            ("location_id", "=", self.location_id.id),
            ("lot_id", "=", self.lot_id.id or False),
            ("package_id", "=", self.package_id.id or False),
            ("owner_id", "=", self.owner_id.id or False),
            ("company_id", "=", self.company_id.id),
        ]

    def _find_quant(self):
        """Return the quant this line refers to, or an empty recordset."""
        self.ensure_one()
        quant_model = self.env["stock.quant"]
        if self.quant_id:
            return quant_model.browse(self.quant_id.id)
        found = quant_model.sudo().search(self._quant_domain(), limit=1)
        return quant_model.browse(found.id) if found else quant_model

    def _create_quant(self):
        """Create the quant for stock found where the system expected none."""
        self.ensure_one()
        quant = (
            self.env["stock.quant"]
            .with_context(inventory_mode=True)
            .create(
                {
                    "product_id": self.product_id.id,
                    "location_id": self.location_id.id,
                    "lot_id": self.lot_id.id or False,
                    "package_id": self.package_id.id or False,
                    "owner_id": self.owner_id.id or False,
                    "inventory_quantity": self.final_qty,
                }
            )
        )
        self.sudo().quant_id = quant
        return quant

    # ------------------------------------------------------------------
    # Applying to stock
    # ------------------------------------------------------------------
    def _check_tracking_before_apply(self):
        """Mirror the core check on tracked products without a lot.

        Core only blocks when stock would be *created* without a lot, which is
        the case that leaves untraceable inventory behind.
        """
        bad_products = self.env["product.product"]
        for line in self.sudo():
            rounding = line.product_id.uom_id.rounding
            if (
                line.product_id.tracking in ("lot", "serial")
                and not line.lot_id
                and float_is_zero(line.theoretical_qty, precision_rounding=rounding)
                and not float_is_zero(line.final_qty, precision_rounding=rounding)
            ):
                bad_products |= line.product_id
        if bad_products:
            raise UserError(
                _(
                    "These products are tracked by lot/serial number and cannot "
                    "be adjusted without one:\n%(products)s",
                    products="\n".join("- %s" % p.display_name for p in bad_products),
                )
            )

    def _apply_to_stock(self):
        """Write the final quantities on the quants and adjust stock.

        Returns a tuple ``(applied, conflicts)``. A conflict is a line whose
        quant moved since the round was created: applying a count computed on a
        stale basis would silently overwrite a legitimate movement, so the line
        is sent back for a recount instead.
        """
        if not self:
            return self.browse(), self.browse()
        self._check_tracking_before_apply()
        inventory = self.mapped("inventory_id")
        inventory.ensure_one()
        create_zero = inventory.create_zero_moves
        applied_ids, conflict_ids, to_adjust = [], [], []
        # ``sudo`` only to read the manager-restricted theoretical quantity;
        # everything that touches stock stays in the caller's environment.
        for line in self.sudo():
            rounding = line.product_id.uom_id.rounding
            quant = line._find_quant()
            if quant:
                if (
                    float_compare(
                        quant.quantity,
                        line.theoretical_qty,
                        precision_rounding=rounding,
                    )
                    != 0
                ):
                    conflict_ids.append(line.id)
                    continue
                unchanged = (
                    float_compare(
                        line.final_qty, quant.quantity, precision_rounding=rounding
                    )
                    == 0
                )
                if unchanged and not create_zero:
                    applied_ids.append(line.id)
                    continue
            else:
                if float_is_zero(line.final_qty, precision_rounding=rounding):
                    # Nothing on the books, nothing counted: nothing to do.
                    applied_ids.append(line.id)
                    continue
                quant = line._create_quant()
            to_adjust.append((line.id, quant.id))

        applied = self.browse(applied_ids)
        conflicts = self.browse(conflict_ids)
        applied |= self._adjust_quants(to_adjust, inventory)
        applied.write({"state": "applied"})
        if conflicts:
            conflicts.write({"note": _("Stock moved during the count.")})
        return applied, conflicts

    def _adjust_quants(self, to_adjust, inventory):
        """Batch the actual adjustment. ``to_adjust`` is a list of id pairs."""
        adjusted = self.browse()
        if not to_adjust:
            return adjusted
        batch = inventory.company_id.stock_inventory_batch_size or 1000
        quant_model = self.env["stock.quant"]
        for chunk in split_every(batch, to_adjust):
            chunk = list(chunk)
            lines = self.browse([pair[0] for pair in chunk])
            quants = quant_model.browse([pair[1] for pair in chunk])
            # Link the quants to the adjustment group so that the resulting
            # moves are stamped with ``inventory_adjustment_id``.
            quants.sudo().write({"current_inventory_id": inventory.id, "to_do": True})
            for line, quant in zip(lines.sudo(), quants):
                quant.with_context(inventory_mode=True).write(
                    {
                        "inventory_quantity": line.final_qty,
                        "inventory_quantity_set": True,
                        "user_id": line.user_id.id or False,
                    }
                )
            quants._apply_inventory()
            quants.sudo().write({"inventory_quantity_set": False})
            adjusted |= lines
        return adjusted

    # ------------------------------------------------------------------
    # Arbitration
    # ------------------------------------------------------------------
    def action_open_arbitrate_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Arbitrate Count"),
            "res_model": "stock.inventory.count.arbitrate",
            "view_mode": "form",
            "target": "new",
            "context": {"active_ids": self.ids, "active_model": self._name},
        }
