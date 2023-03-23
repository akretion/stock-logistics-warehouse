from odoo.tests.common import Form, TransactionCase

class TestPartnerWarehouse(TransactionCase):

    def setUp(self):
        super(TestPartnerWarehouse, self).setUp()
        self.order = self.env["sale.order"]

        self.wh1 = self.env["stock.warehouse"].create(
            {
                "name": "Warehouse_test_1",
                "code": "WHT1",
            }
        )
        self.wh2 = self.env["stock.warehouse"].create(
            {
                "name": "Warehouse_test_2",
                "code": "WHT2",
            }
        )
        self.partner1 = self.env.ref("base.res_partner_3")
        self.partner1.write(
            {
                "partner_supply_warehouse_id": self.wh1,
            }
        )
        self.partner2 = self.env.ref("base.res_partner_address_10")
        self.partner2.write(
            {
                "partner_supply_warehouse_id": self.wh2,
            }
        )
        self.partner3 = self.env["res.partner"].create(
            {
                "name": "TestPartner3",
                "company_type" : "person",
                "parent_id" :self.partner1.id,
            }
        )
    
    #in this first test, we test "_onchange_partner_shinpping_warehouse_id" in a partner_supply_warehouse_id
    def test_1_autofill_partner_warehouse_id(self):
        view_id = "sale.view_order_form"
        with Form(self.order, view = view_id) as SaleOrder1Test:
            SaleOrder1Test.partner_id = self.partner1
            order = SaleOrder1Test.save()
        self.assertEqual(self.order.warehouse_id.id, self.order.partner_shipping_id.partner_supply_warehouse_id.id)

    #in this second test, we test "_onchange_partner_shinpping_warehouse_id" in a partner_supply_warehouse_id if the 
    # partner_shipping_id's warehouse is different from the partner_id
    def test_2_autofill_partner_warehouse_id(self):
        view_id = "sale.view_order_form"
        with Form(self.order, view = view_id) as SaleOrder2Test:
            SaleOrder2Test.partner_id = self.partner1
            SaleOrder2Test.partner_shipping_id = self.partner2
        order = SaleOrder2Test.save()
        self.assertEqual(self.order.warehouse_id.id, self.order.partner_shipping_id.partner_supply_warehouse_id.id)

    #in this third test, we test "_onchange_partner_shinpping_warehouse_id" in a partner_supply_warehouse_id if the 
    # partner of the partner_shipping_id's warehouse is empty : in this case , take the warehouse of the parent
    def test_3_autofill_partner_warehouse_id(self):
        view_id = "sale.view_order_form"
        with Form(self.order, view = view_id) as SaleOrder3Test:
            SaleOrder3Test.partner_id = self.partner1
            SaleOrder3Test.partner_shipping_id = self.partner3
        order = SaleOrder3Test.save()
        self.assertEqual(self.order.warehouse_id.id, self.order.partner_id.partner_supply_warehouse_id.id)
