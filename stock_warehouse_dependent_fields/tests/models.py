# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models

# pylint: disable=consider-merging-classes-inherited


class FakeResPartner(models.Model):
    _inherit = "res.partner"

    test_supplier_delay = fields.Integer(warehouse_dependent=True)
