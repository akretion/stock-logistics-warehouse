# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests.common import TransactionCase


class TestWarehouseUsers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_default_user_warehouse(self):
        # test default value (post install script)
        admin = self.env.ref("base.user_admin")
        wh1 = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)]
        )
        self.assertEqual(admin.warehouse_id, wh1)
        # test default value in case of new company
        new_company = self.env["res.company"].create({"name": "test"})
        new_wh = self.env["stock.warehouse"].search(
            [("company_id", "=", new_company.id)]
        )
        self.assertEqual(admin.with_company(new_company.id).warehouse_id, new_wh)
