{
    "name": "Supplier Management",
    "version": "19.0.1.0.0",
    "summary": "Supplier performance analytics on top of purchase receipts",
    "category": "Custom_Odoo",
    "author": "Tony",
    "license": "LGPL-3",
    "depends": ["purchase_stock", "warehouse_management"],
    "data": [
        "security/supplier_security.xml",
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": True,
}
