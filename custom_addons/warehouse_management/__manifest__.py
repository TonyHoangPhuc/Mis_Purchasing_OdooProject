{
    "name": "Warehouse Management",
    "version": "19.0.1.0.0",
    "summary": "Inbound QC and discrepancy control for warehouse receipts",
    "category": "Custom_Odoo",
    "author": "Tony",
    "license": "LGPL-3",
    "depends": ["stock", "purchase_stock", "web"],
    "data": [
        "security/warehouse_security.xml",
        "security/ir.model.access.csv",
        "views/stock_picking_views.xml",
        "views/menu_integration_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "warehouse_management/static/src/js/app_switcher_toggle.js",
            "warehouse_management/static/src/xml/app_switcher_toggle.xml",
            "warehouse_management/static/src/scss/app_switcher_toggle.scss",
        ],
    },
    "installable": True,
    "application": True,
}
