from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    mis_role = fields.Selection(
        [
            ("central", "Kho tổng"),
            ("store", "Kho cửa hàng"),
        ],
        string="Vai trò kho",
        default="central",
        required=True,
        copy=False,
    )
    store_record_id = fields.Many2one(
        "store.store",
        string="Cửa hàng liên kết",
        copy=False,
        readonly=True,
    )
