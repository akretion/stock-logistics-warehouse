{
    "name": "Stock Warehouse Users",
    "summary": """Assign a warehouse to each users and a list of allowed warehouse""",
    "maintainers": ["florian-dacosta"],
    "version": "16.0.1.0.0",
    "depends": ["stock"],
    "data": ["views/res_users.xml"],
    "license": "LGPL-3",
    "website": "https://github.com/OCA/stock-logistics-warehouse",
    "author": "Akretion, " "Odoo Community Association (OCA)",
    "category": "Warehouse Management",
    "post_init_hook": "set_default_warehouse_property",
}
