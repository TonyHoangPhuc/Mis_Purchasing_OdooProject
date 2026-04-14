{
    "name": "Warehouse Management",
    "version": "19.0.1.0.0",
    "summary": "Kiểm soát QC đầu vào và sai lệch cho phiếu nhập kho",
    "category": "Custom_Odoo",
    "author": "Tony",
    "license": "LGPL-3",
    "depends": ["stock", "purchase_stock", "web", "merchandise_management"],
    "data": [
        "security/warehouse_security.xml",
        "security/ir.model.access.csv",
        "views/stock_picking_views.xml",
        "views/merchandise_integration_views.xml",
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
