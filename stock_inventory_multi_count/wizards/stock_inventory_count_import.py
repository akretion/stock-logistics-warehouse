# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import csv
import io
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DELIMITERS = {"semicolon": ";", "comma": ",", "tab": "\t"}


class StockInventoryCountImport(models.TransientModel):
    _name = "stock.inventory.count.import"
    _description = "Import Inventory Counts"

    round_id = fields.Many2one(
        comodel_name="stock.inventory.count.round",
        string="Count Round",
        required=True,
        readonly=True,
    )
    data_file = fields.Binary(string="CSV File")
    filename = fields.Char()
    paste_data = fields.Text(
        string="Or paste the counts here",
        help="One line per count. Same columns as the file.",
    )
    delimiter = fields.Selection(
        selection=[
            ("semicolon", "Semicolon (;)"),
            ("comma", "Comma (,)"),
            ("tab", "Tab"),
        ],
        default="semicolon",
        required=True,
    )
    has_header = fields.Boolean(string="First line is a header", default=True)
    create_missing_lines = fields.Boolean(
        string="Create lines for unexpected stock",
        default=True,
        help="Add a line when the file reports a product/location the system "
        "did not expect to find there.",
    )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def _get_rows(self):
        self.ensure_one()
        if self.data_file:
            try:
                content = base64.b64decode(self.data_file).decode("utf-8-sig")
            except UnicodeDecodeError:
                content = base64.b64decode(self.data_file).decode("latin-1")
        elif self.paste_data:
            content = self.paste_data
        else:
            raise UserError(_("Provide a file or paste the counts."))
        reader = csv.reader(io.StringIO(content), delimiter=DELIMITERS[self.delimiter])
        rows = [row for row in reader if any(cell.strip() for cell in row)]
        if self.has_header and rows:
            rows = rows[1:]
        return rows

    def _build_caches(self):
        """Index the round lines and the reference data used for matching."""
        self.ensure_one()
        lines_by_key = {}
        for line in self.round_id.line_ids:
            key = (
                line.product_id.id,
                line.location_id.id,
                line.lot_id.id or False,
            )
            lines_by_key[key] = line
        return lines_by_key

    def _find_location(self, token):
        token = (token or "").strip()
        if not token:
            raise UserError(_("A location is required on every row."))
        location_model = self.env["stock.location"]
        company_domain = [
            "|",
            ("company_id", "=", self.round_id.company_id.id),
            ("company_id", "=", False),
        ]
        for field in ("barcode", "complete_name", "name"):
            location = location_model.search(
                [(field, "=", token), ("usage", "in", ["internal", "transit"])]
                + company_domain,
                limit=1,
            )
            if location:
                return location
        raise UserError(_("Location not found: %s", token))

    def _find_product(self, token):
        token = (token or "").strip()
        if not token:
            raise UserError(_("A product is required on every row."))
        product_model = self.env["product.product"]
        for field in ("default_code", "barcode", "name"):
            product = product_model.search(
                [(field, "=", token), ("type", "=", "product")], limit=1
            )
            if product:
                return product
        raise UserError(_("Product not found: %s", token))

    def _find_lot(self, token, product):
        token = (token or "").strip()
        if not token:
            return self.env["stock.lot"]
        lot = self.env["stock.lot"].search(
            [
                ("name", "=", token),
                ("product_id", "=", product.id),
                ("company_id", "=", self.round_id.company_id.id),
            ],
            limit=1,
        )
        if not lot:
            raise UserError(
                _(
                    "Lot/serial %(lot)s not found for product %(product)s.",
                    lot=token,
                    product=product.display_name,
                )
            )
        return lot

    @staticmethod
    def _parse_qty(token):
        token = (token or "").strip().replace(" ", "")
        if not token:
            raise UserError(_("A quantity is required on every row."))
        # Accept both "1.234,50" and "1234.50"
        if "," in token and "." in token:
            token = token.replace(".", "").replace(",", ".")
        elif "," in token:
            token = token.replace(",", ".")
        try:
            return float(token)
        except ValueError as err:
            raise UserError(_("Invalid quantity: %s", token)) from err

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------
    def action_import(self):
        self.ensure_one()
        if self.round_id.state != "in_progress":
            raise UserError(_("This round is not open for counting."))
        rows = self._get_rows()
        lines_by_key = self._build_caches()
        line_model = self.env["stock.inventory.count.line"]
        updated, created = 0, 0
        first_row_number = 2 if self.has_header else 1
        for index, row in enumerate(rows, start=first_row_number):
            if len(row) < 3:
                raise UserError(
                    _(
                        "Row %(row)s has %(count)s columns, at least 3 are "
                        "required (location, product, quantity).",
                        row=index,
                        count=len(row),
                    )
                )
            location = self._find_location(row[0])
            product = self._find_product(row[1])
            if len(row) >= 4:
                lot = self._find_lot(row[2], product)
                qty = self._parse_qty(row[3])
            else:
                lot = self.env["stock.lot"]
                qty = self._parse_qty(row[2])
            key = (product.id, location.id, lot.id or False)
            line = lines_by_key.get(key)
            if not line:
                if not self.create_missing_lines:
                    raise UserError(
                        _(
                            "Row %(row)s does not match any line of this round "
                            "and the creation of new lines is disabled.",
                            row=index,
                        )
                    )
                line = line_model.create(
                    {
                        "round_id": self.round_id.id,
                        "product_id": product.id,
                        "location_id": location.id,
                        "lot_id": lot.id or False,
                        "theoretical_qty": 0.0,
                        "state": "pending",
                    }
                )
                lines_by_key[key] = line
                created += 1
            else:
                updated += 1
            line.counted_qty = qty
        self.round_id.inventory_id.message_post(
            body=_(
                "Counts imported into round %(number)s: %(updated)s lines "
                "updated, %(created)s lines created.",
                number=self.round_id.round_number,
                updated=updated,
                created=created,
            )
        )
        return {"type": "ir.actions.act_window_close"}
