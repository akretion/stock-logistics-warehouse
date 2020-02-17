# -*- coding: utf-8 -*-
# Copyright (C) 2019 Akretion
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    "name": "Base Multi Warehouse",
    "version": "8.0.1.0.0",
    "category": "Warehouse Management",
    "website": "https://github.com/OCA/stock-logistics-warehouse",
    "author": "Akretion, Odoo Community Association (OCA)",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "summary": "Add Warehouse field in Users",
    "description": "Add Warehouse field in Users",
    "depends": [
        "stock",
    ],
    "data": [
        'views/res_users.xml',
    ],
    "post_init_hook": "post_init_hook",
}
