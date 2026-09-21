# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Stock Inventory Multi Count",
    "summary": "Blind multi-round inventory counting with automatic recount "
    "of divergent lines",
    "version": "16.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "Akretion, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-warehouse",
    "license": "AGPL-3",
    "development_status": "Alpha",
    "depends": ["stock_inventory"],
    "data": [
        "security/stock_inventory_multi_count_security.xml",
        "security/ir.model.access.csv",
        "wizards/stock_inventory_count_import_views.xml",
        "wizards/stock_inventory_count_arbitrate_views.xml",
        "views/stock_inventory_count_line_views.xml",
        "views/stock_inventory_count_round_views.xml",
        "views/stock_inventory_views.xml",
        "views/res_config_settings_views.xml",
        "reports/stock_inventory_count_sheet.xml",
        "reports/report_action.xml",
    ],
    "installable": True,
    "application": False,
}
