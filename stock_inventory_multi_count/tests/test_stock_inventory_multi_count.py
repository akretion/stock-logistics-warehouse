# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestStockInventoryMultiCount(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("base.main_company")
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.shelf_a = cls.env["stock.location"].create(
            {
                "name": "Shelf A",
                "usage": "internal",
                "location_id": cls.stock_location.id,
            }
        )
        cls.shelf_b = cls.env["stock.location"].create(
            {
                "name": "Shelf B",
                "usage": "internal",
                "location_id": cls.stock_location.id,
            }
        )
        cls.product_a = cls.env["product.product"].create(
            {"name": "Product A", "type": "product", "standard_price": 10.0}
        )
        cls.product_b = cls.env["product.product"].create(
            {"name": "Product B", "type": "product", "standard_price": 100.0}
        )
        cls.product_new = cls.env["product.product"].create(
            {"name": "Product Never Stocked", "type": "product"}
        )

        group_manager = cls.env.ref("stock.group_stock_manager")
        group_counter = cls.env.ref(
            "stock_inventory_multi_count.group_stock_inventory_counter"
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Inventory Manager",
                "login": "multi_count_manager",
                "email": "manager@example.com",
                "groups_id": [
                    (6, 0, [cls.env.ref("base.group_user").id, group_manager.id])
                ],
            }
        )
        cls.counter_1 = cls.env["res.users"].create(
            {
                "name": "Counter One",
                "login": "multi_count_counter_1",
                "email": "counter1@example.com",
                "groups_id": [
                    (6, 0, [cls.env.ref("base.group_user").id, group_counter.id])
                ],
            }
        )
        cls.counter_2 = cls.env["res.users"].create(
            {
                "name": "Counter Two",
                "login": "multi_count_counter_2",
                "email": "counter2@example.com",
                "groups_id": [
                    (6, 0, [cls.env.ref("base.group_user").id, group_counter.id])
                ],
            }
        )

        cls._set_stock(cls.product_a, cls.shelf_a, 100.0)
        cls._set_stock(cls.product_b, cls.shelf_b, 50.0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _set_stock(cls, product, location, qty):
        cls.env["stock.quant"]._update_available_quantity(product, location, qty)

    def _new_inventory(self, **kwargs):
        vals = {
            "name": "Blind Count Test",
            "count_mode": "multi",
            "product_selection": "all",
            "location_ids": [(6, 0, [self.shelf_a.id, self.shelf_b.id])],
            "company_id": self.company.id,
        }
        vals.update(kwargs)
        return self.env["stock.inventory"].with_user(self.manager).create(vals)

    def _line(self, inventory, product, round_number=None):
        domain = [
            ("inventory_id", "=", inventory.id),
            ("product_id", "=", product.id),
        ]
        if round_number:
            domain.append(("round_number", "=", round_number))
        return (
            self.env["stock.inventory.count.line"]
            .with_user(self.manager)
            .search(domain, order="round_number desc", limit=1)
        )

    def _count(self, line, qty, user=None):
        line.with_user(user or self.manager).counted_qty = qty

    def _quant(self, product, location):
        return self.env["stock.quant"].search(
            [("product_id", "=", product.id), ("location_id", "=", location.id)],
            limit=1,
        )

    # ------------------------------------------------------------------
    # Round generation
    # ------------------------------------------------------------------
    def test_start_generates_first_round(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        self.assertEqual(len(inventory.round_ids), 1)
        count_round = inventory.round_ids
        self.assertEqual(count_round.round_number, 1)
        self.assertEqual(count_round.state, "in_progress")
        self.assertEqual(len(count_round.line_ids), 2)
        line_a = self._line(inventory, self.product_a)
        self.assertEqual(line_a.theoretical_qty, 100.0)
        self.assertFalse(line_a.counted)
        self.assertEqual(line_a.state, "pending")

    def test_single_mode_untouched(self):
        """A plain single count adjustment keeps the stock behaviour."""
        inventory = self._new_inventory(count_mode="single")
        inventory.action_state_to_in_progress()
        self.assertFalse(inventory.round_ids)
        self.assertTrue(inventory.stock_quant_ids)

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    def test_round1_all_matching_closes_inventory(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 100.0)
        self._count(self._line(inventory, self.product_b), 50.0)
        inventory.action_close_current_round()
        self.assertEqual(inventory.state, "done")
        self.assertEqual(len(inventory.round_ids), 1)
        self.assertEqual(self._quant(self.product_a, self.shelf_a).quantity, 100.0)

    def test_divergence_creates_second_round(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 95.0, self.counter_1)
        self._count(self._line(inventory, self.product_b), 50.0, self.counter_1)
        inventory.action_close_current_round()

        self.assertEqual(inventory.state, "in_progress")
        self.assertEqual(len(inventory.round_ids), 2)
        round_2 = inventory.round_ids.filtered(lambda r: r.round_number == 2)
        self.assertEqual(len(round_2.line_ids), 1)
        line_2 = round_2.line_ids
        self.assertEqual(line_2.product_id, self.product_a)
        self.assertEqual(line_2.previous_qty, 95.0)
        self.assertEqual(line_2.previous_user_id, self.counter_1)
        # The matching line was applied, the divergent one superseded.
        line_1_b = self._line(inventory, self.product_b, round_number=1)
        self.assertEqual(line_1_b.state, "applied")
        line_1_a = self._line(inventory, self.product_a, round_number=1)
        self.assertEqual(line_1_a.state, "superseded")
        # Nothing was adjusted for the divergent product yet.
        self.assertEqual(self._quant(self.product_a, self.shelf_a).quantity, 100.0)

    def test_second_count_confirms_first_and_adjusts(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 95.0, self.counter_1)
        self._count(self._line(inventory, self.product_b), 50.0, self.counter_1)
        inventory.action_close_current_round()

        line_2 = self._line(inventory, self.product_a, round_number=2)
        self._count(line_2, 95.0, self.counter_2)
        inventory.action_close_current_round()

        self.assertEqual(inventory.state, "done")
        # The count wins over the system quantity, never the other way around.
        self.assertEqual(self._quant(self.product_a, self.shelf_a).quantity, 95.0)
        self.assertEqual(line_2.state, "applied")

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    def test_same_counter_is_refused_on_recount(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 95.0, self.counter_1)
        self._count(self._line(inventory, self.product_b), 50.0, self.counter_1)
        inventory.action_close_current_round()

        line_2 = self._line(inventory, self.product_a, round_number=2)
        with self.assertRaises(UserError):
            self._count(line_2, 95.0, self.counter_1)

    def test_same_counter_allowed_when_disabled(self):
        inventory = self._new_inventory(require_different_counter=False)
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 95.0, self.counter_1)
        self._count(self._line(inventory, self.product_b), 50.0, self.counter_1)
        inventory.action_close_current_round()
        line_2 = self._line(inventory, self.product_a, round_number=2)
        self._count(line_2, 95.0, self.counter_1)
        self.assertTrue(line_2.counted)

    def test_max_rounds_leads_to_arbitration(self):
        inventory = self._new_inventory(max_rounds=2)
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 95.0, self.counter_1)
        self._count(self._line(inventory, self.product_b), 50.0, self.counter_1)
        inventory.action_close_current_round()

        line_2 = self._line(inventory, self.product_a, round_number=2)
        self._count(line_2, 97.0, self.counter_2)
        inventory.action_close_current_round()

        self.assertEqual(inventory.state, "arbitration")
        self.assertEqual(len(inventory.round_ids), 2)
        self.assertEqual(line_2.state, "divergent")
        self.assertEqual(self._quant(self.product_a, self.shelf_a).quantity, 100.0)

    def test_arbitration_applies_supervised_quantity(self):
        inventory = self._new_inventory(max_rounds=2)
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 95.0, self.counter_1)
        self._count(self._line(inventory, self.product_b), 50.0, self.counter_1)
        inventory.action_close_current_round()
        line_2 = self._line(inventory, self.product_a, round_number=2)
        self._count(line_2, 97.0, self.counter_2)
        inventory.action_close_current_round()

        wizard = (
            self.env["stock.inventory.count.arbitrate"]
            .with_user(self.manager)
            .with_context(
                active_model="stock.inventory.count.line", active_ids=line_2.ids
            )
            .create(
                {
                    "resolution": "manual",
                    "manual_qty": 96.0,
                    "note": "Supervised recount",
                }
            )
        )
        wizard.action_confirm()

        self.assertEqual(self._quant(self.product_a, self.shelf_a).quantity, 96.0)
        self.assertEqual(line_2.state, "applied")
        self.assertEqual(line_2.arbitrated_by_id, self.manager)
        self.assertEqual(inventory.state, "done")

    def test_arbitration_requires_manager(self):
        inventory = self._new_inventory(max_rounds=1)
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 95.0, self.counter_1)
        self._count(self._line(inventory, self.product_b), 50.0, self.counter_1)
        inventory.action_close_current_round()
        line = self._line(inventory, self.product_a, round_number=1)
        wizard = (
            self.env["stock.inventory.count.arbitrate"]
            .sudo()
            .with_context(
                active_model="stock.inventory.count.line", active_ids=line.ids
            )
            .create({"resolution": "counted", "note": "x"})
        )
        with self.assertRaises(UserError):
            wizard.with_user(self.counter_1)._check_access()

    # ------------------------------------------------------------------
    # Tolerance
    # ------------------------------------------------------------------
    def test_tolerance_qty_absorbs_small_gap(self):
        inventory = self._new_inventory(tolerance_type="qty", tolerance_value=2.0)
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 99.0)
        self._count(self._line(inventory, self.product_b), 50.0)
        inventory.action_close_current_round()
        self.assertEqual(inventory.state, "done")
        # Within tolerance still means the count is applied, not ignored.
        self.assertEqual(self._quant(self.product_a, self.shelf_a).quantity, 99.0)

    def test_tolerance_percent(self):
        inventory = self._new_inventory(tolerance_type="percent", tolerance_value=5.0)
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 96.0)  # 4% off
        self._count(self._line(inventory, self.product_b), 40.0)  # 20% off
        inventory.action_close_current_round()
        self.assertEqual(inventory.state, "in_progress")
        round_2 = inventory.round_ids.filtered(lambda r: r.round_number == 2)
        self.assertEqual(round_2.line_ids.product_id, self.product_b)

    def test_tolerance_value(self):
        # 1 unit of A is worth 10, 1 unit of B is worth 100.
        inventory = self._new_inventory(tolerance_type="value", tolerance_value=50.0)
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 96.0)  # 40 of value
        self._count(self._line(inventory, self.product_b), 49.0)  # 100 of value
        inventory.action_close_current_round()
        round_2 = inventory.round_ids.filtered(lambda r: r.round_number == 2)
        self.assertEqual(round_2.line_ids.product_id, self.product_b)

    def test_first_round_criterion_none_forces_second_count(self):
        inventory = self._new_inventory(first_round_criterion="none")
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 100.0, self.counter_1)
        self._count(self._line(inventory, self.product_b), 50.0, self.counter_1)
        inventory.action_close_current_round()
        self.assertEqual(inventory.state, "in_progress")
        round_2 = inventory.round_ids.filtered(lambda r: r.round_number == 2)
        self.assertEqual(len(round_2.line_ids), 2)

    # ------------------------------------------------------------------
    # Uncounted lines
    # ------------------------------------------------------------------
    def test_uncounted_blocks_by_default(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 100.0)
        with self.assertRaises(UserError):
            inventory.action_close_current_round()

    def test_uncounted_as_zero(self):
        inventory = self._new_inventory(uncounted_policy="zero")
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 100.0)
        inventory.action_close_current_round()
        # B was never counted: treated as zero, so it diverges and is recounted.
        round_2 = inventory.round_ids.filtered(lambda r: r.round_number == 2)
        self.assertEqual(round_2.line_ids.product_id, self.product_b)
        self.assertEqual(round_2.line_ids.previous_qty, 0.0)

    def test_uncounted_keeps_theoretical(self):
        inventory = self._new_inventory(uncounted_policy="theoretical")
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 100.0)
        inventory.action_close_current_round()
        self.assertEqual(inventory.state, "done")
        self.assertEqual(self._quant(self.product_b, self.shelf_b).quantity, 50.0)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------
    def test_unexpected_stock_creates_quant(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        count_round = inventory.round_ids
        found = (
            self.env["stock.inventory.count.line"]
            .with_user(self.manager)
            .create(
                {
                    "round_id": count_round.id,
                    "product_id": self.product_new.id,
                    "location_id": self.shelf_a.id,
                    "theoretical_qty": 0.0,
                }
            )
        )
        self._count(found, 7.0)
        self._count(self._line(inventory, self.product_a), 100.0)
        self._count(self._line(inventory, self.product_b), 50.0)
        inventory.action_close_current_round()
        # Counted 7 against a theoretical 0: that is a divergence, recounted.
        round_2 = inventory.round_ids.filtered(lambda r: r.round_number == 2)
        self.assertEqual(round_2.line_ids.product_id, self.product_new)
        self._count(round_2.line_ids, 7.0, self.counter_2)
        inventory.action_close_current_round()
        self.assertEqual(self._quant(self.product_new, self.shelf_a).quantity, 7.0)

    def test_movement_during_count_is_a_conflict(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        self._count(self._line(inventory, self.product_a), 95.0)
        self._count(self._line(inventory, self.product_b), 50.0)
        # Somebody ships 10 units while the count is running.
        self._set_stock(self.product_b, self.shelf_b, -10.0)
        inventory.action_close_current_round()
        round_2 = inventory.round_ids.filtered(lambda r: r.round_number == 2)
        self.assertIn(self.product_b, round_2.line_ids.product_id)
        line_1_b = self._line(inventory, self.product_b, round_number=1)
        self.assertEqual(line_1_b.state, "superseded")
        # The movement was not overwritten.
        self.assertEqual(self._quant(self.product_b, self.shelf_b).quantity, 40.0)

    def test_counter_cannot_read_theoretical_quantity(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        line = self._line(inventory, self.product_a)
        line.round_id.sudo().user_ids = [(6, 0, [self.counter_1.id])]
        counter_line = line.with_user(self.counter_1)
        with self.assertRaises(AccessError):
            counter_line.read(["theoretical_qty"])
        # but the counter can read and write what they need
        self.assertTrue(counter_line.read(["product_id", "counted_qty"]))

    def test_counter_only_sees_own_round(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        count_round = inventory.round_ids
        count_round.sudo().user_ids = [(6, 0, [self.counter_1.id])]
        visible = (
            self.env["stock.inventory.count.line"]
            .with_user(self.counter_2)
            .search([("round_id", "=", count_round.id)])
        )
        self.assertFalse(visible)
        visible_1 = (
            self.env["stock.inventory.count.line"]
            .with_user(self.counter_1)
            .search([("round_id", "=", count_round.id)])
        )
        self.assertEqual(len(visible_1), 2)

    def test_back_to_draft_clears_rounds(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        self.assertTrue(inventory.round_ids)
        inventory.action_state_to_draft()
        self.assertFalse(inventory.round_ids)
        self.assertFalse(inventory.count_line_ids)

    def test_cancel_releases_quants(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        quants = inventory.stock_quant_ids
        self.assertTrue(all(q.to_do for q in quants))
        inventory.action_state_to_cancel()
        self.assertEqual(inventory.state, "cancel")
        self.assertFalse(any(q.to_do for q in quants))
        self.assertTrue(all(r.state == "cancel" for r in inventory.round_ids))

    def test_import_wizard(self):
        inventory = self._new_inventory()
        inventory.action_state_to_in_progress()
        count_round = inventory.round_ids
        self.product_a.default_code = "PROD-A"
        self.product_b.default_code = "PROD-B"
        data = "location;product;qty\n%s;PROD-A;100\n%s;PROD-B;48" % (
            self.shelf_a.complete_name,
            self.shelf_b.complete_name,
        )
        wizard = (
            self.env["stock.inventory.count.import"]
            .with_user(self.manager)
            .create({"round_id": count_round.id, "paste_data": data})
        )
        wizard.action_import()
        self.assertEqual(self._line(inventory, self.product_a).counted_qty, 100.0)
        self.assertEqual(self._line(inventory, self.product_b).counted_qty, 48.0)
        self.assertTrue(self._line(inventory, self.product_b).counted)
