# Copyright (C) 2019 Akretion
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    "name": "Base Multi Warehouse",
    "version": "12.0.1.0.0",
    "category": "Warehouse Management",
    "website": "https://github.com/OCA/stock-logistics-warehouse",
    "author": "Akretion, Odoo Community Association (OCA)",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "summary": "Add warehouse on user and switch between allowed warehouses",
    "depends": [
        "stock",
    ],
    "data": [
        'views/res_users.xml',
    ],
}
