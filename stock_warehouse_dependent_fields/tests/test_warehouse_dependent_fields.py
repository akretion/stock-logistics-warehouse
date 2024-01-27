# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo_test_helper import FakeModelLoader

from odoo.tests.common import TransactionCase


class TestWarehouseDependentFields(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loader = FakeModelLoader(cls.env, cls.__module__)
        cls.loader.backup_registry()

        # The fake class is imported here !! After the backup_registry
        from .models import FakeResPartner

        cls.loader.update_registry((FakeResPartner,))
        cls.partner = cls.env.ref("base.res_partner_1")
        cls.wh1 = cls.env.ref("stock.warehouse0")
        cls.wh2 = cls.env["stock.warehouse"].create(
            {"name": "Second warehouse", "code": "TEST"}
        )
        cls.user2 = cls.env.ref("base.user_demo")
        cls.user2.write({"property_warehouse_id": cls.wh2.id})

    @classmethod
    def tearDownClass(cls):
        cls.loader.restore_registry()
        super().tearDownClass()

    def test_warehouse_dependent_fields(self):
        partner = self.partner
        wh1 = self.wh1
        wh2 = self.wh2
        user2 = self.user2
        partner.write({"test_supplier_delay": 12})
        partner.with_context(force_warehouse=wh2.id).write({"test_supplier_delay": 10})
        self.assertEqual(partner.test_supplier_delay, 12)
        self.assertEqual(
            partner.with_context(force_warehouse=wh1.id).test_supplier_delay, 12
        )
        self.assertEqual(
            partner.with_context(force_warehouse=wh2.id).test_supplier_delay, 10
        )
        self.assertEqual(partner.with_user(user2.id).test_supplier_delay, 10)
        self.env.user.write({"property_warehouse_id": wh2.id})
        self.assertEqual(partner.test_supplier_delay, 10)
        self.env.user.write({"property_warehouse_id": wh1.id})

        partner.invalidate_cache()
        self.assertEqual(partner.test_supplier_delay, 12)
        self.assertEqual(partner.with_user(user2.id).test_supplier_delay, 10)
        self.assertEqual(
            partner.with_context(force_warehouse=wh1.id).test_supplier_delay, 12
        )

    def test_default_warehouse_dependent_value(self):
        partner = self.partner
        self.env["ir.property"]._set_default_wh(
            "test_supplier_delay", "res.partner", 15
        )
        self.assertEqual(partner.test_supplier_delay, 15)
        partner.write({"test_supplier_delay": 2})
        self.assertEqual(partner.test_supplier_delay, 2)
        self.assertEqual(
            partner.with_context(force_warehouse=self.wh2.id).test_supplier_delay, 15
        )
