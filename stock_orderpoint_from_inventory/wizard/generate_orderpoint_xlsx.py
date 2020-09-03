# Copyright 2020 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class GenerateOrderpoint(models.TransientModel):
    """ Trivial wizard to present the generated excel file to the user """

    _name = "generate.orderpoint.xlsx"

    filename = fields.Char()
    file = fields.Binary()
