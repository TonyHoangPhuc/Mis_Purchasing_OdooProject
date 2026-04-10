{
    "name": "MER Simulation Request",
    "version": "19.0.1.0.0",
    "summary": "Simulate merchandise requests and integrate them with purchase and supply chain",
    "category": "Custom_Odoo",
    "author": "Tony",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "purchase_stock",
        "warehouse_management",
        "supply_chain_management",
        "supplier_management",
    ],
    "data": [
        "security/mer_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "views/mer_purchase_request_views.xml",
        "views/menu_integration_views.xml",
    ],
    "installable": True,
    "application": True,
}
