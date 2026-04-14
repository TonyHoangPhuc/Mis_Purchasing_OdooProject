from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    scm_allocation_plan_id = fields.Many2one(
        "supply.chain.allocation.plan",
        string="Kế hoạch phân bổ",
        copy=False,
        readonly=True,
    )
    scm_is_store_delivery = fields.Boolean(
        string="Giao cửa hàng",
        compute="_compute_scm_is_store_delivery",
    )

    @api.depends("picking_type_code", "location_id", "location_dest_id")
    def _compute_scm_is_store_delivery(self):
        for picking in self:
            source_warehouse = picking.location_id.warehouse_id
            destination_warehouse = picking.location_dest_id.warehouse_id
            picking.scm_is_store_delivery = bool(
                picking.picking_type_code == "internal"
                and source_warehouse
                and destination_warehouse
                and source_warehouse.mis_role == "central"
                and destination_warehouse.mis_role == "store"
            )

    def action_cancel(self):
        store_deliveries = self.filtered("scm_is_store_delivery")
        if store_deliveries:
            raise UserError(
                _(
                    "Phiếu giao từ Kho tổng sang Cửa hàng không được phép từ chối hoặc hủy. "
                    "Supply Chain chỉ xác nhận giao hàng."
                )
            )
        return super().action_cancel()
