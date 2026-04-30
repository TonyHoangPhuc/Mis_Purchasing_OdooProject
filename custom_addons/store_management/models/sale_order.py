from odoo import api, fields, models
from collections import defaultdict


class SaleOrder(models.Model):
    _inherit = "sale.order"

    store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng bán",
        tracking=True,
    )
    store_stock_location_id = fields.Many2one(
        "stock.location",
        string="Vị trí tồn cửa hàng",
        related="warehouse_id.lot_stock_id",
        readonly=True,
    )
    x_available_product_ids = fields.Many2many(
        "product.product",
        compute="_compute_store_available_products",
        string="Sản phẩm có sẵn tại cửa hàng",
    )

    def _get_sale_store(self):
        self.ensure_one()
        return self.store_id or self.warehouse_id.store_record_id

    def _get_sale_store_products(self):
        self.ensure_one()
        store = self._get_sale_store()
        if not store:
            return self.env["product.product"]
        active_products = store.product_line_ids.filtered("active").mapped("product_id")
        if not active_products or not store.warehouse_id or not store.warehouse_id.lot_stock_id:
            return self.env["product.product"]

        available_qty_by_product = defaultdict(float)
        quants = self.env["stock.quant"].sudo().search(
            [
                ("product_id", "in", active_products.ids),
                ("location_id", "child_of", store.warehouse_id.lot_stock_id.id),
            ]
        )
        for quant in quants:
            available_qty_by_product[quant.product_id.id] += quant.available_quantity

        available_product_ids = [
            product_id
            for product_id, available_qty in available_qty_by_product.items()
            if available_qty > 0
        ]
        return self.env["product.product"].browse(available_product_ids)

    @api.onchange("store_id")
    def _onchange_store_id(self):
        if self.store_id:
            self.warehouse_id = self.store_id.warehouse_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("store_id") and not vals.get("warehouse_id"):
                store = self.env["store.store"].browse(vals["store_id"])
                vals["warehouse_id"] = store.warehouse_id.id
        return super().create(vals_list)

    @api.depends(
        "store_id",
        "store_id.product_line_ids",
        "store_id.product_line_ids.active",
        "store_id.product_line_ids.product_id",
        "warehouse_id",
        "warehouse_id.store_record_id",
    )
    def _compute_store_available_products(self):
        for order in self:
            order.x_available_product_ids = order._get_sale_store_products()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sale_store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng bán",
        related="order_id.store_id",
        readonly=True,
    )
    x_available_product_ids = fields.Many2many(
        "product.product",
        compute="_compute_store_available_products",
        string="Sản phẩm có sẵn tại cửa hàng",
    )

    @api.depends(
        "sale_store_id",
        "sale_store_id.product_line_ids",
        "sale_store_id.product_line_ids.active",
        "sale_store_id.product_line_ids.product_id",
        "order_id.warehouse_id",
    )
    def _compute_store_available_products(self):
        for line in self:
            line.x_available_product_ids = line.order_id._get_sale_store_products()
