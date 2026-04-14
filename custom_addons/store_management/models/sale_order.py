from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng bán",
        tracking=True,
    )

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
