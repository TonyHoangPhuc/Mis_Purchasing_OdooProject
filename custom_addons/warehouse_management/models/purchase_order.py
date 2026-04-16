from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    mer_request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yêu cầu Merchandise",
        compute="_compute_mer_request_id",
        compute_sudo=True,
        store=True,
        index=True,
    )
    wm_store_receipt_status = fields.Selection(
        [
            ("no_receipt", "Chưa có phiếu nhận"),
            ("pending_qc", "Chờ cửa hàng nhận và QC"),
            ("received", "Đã nhận hàng"),
            ("defective", "Hàng lỗi"),
        ],
        string="Trạng thái nhận hàng",
        compute="_compute_wm_store_receipt_status",
    )

    @api.depends("origin")
    def _compute_mer_request_id(self):
        requests_by_purchase = {}
        if self.ids:
            purchase_requests = self.env["mer.purchase.request"].sudo().search([("purchase_id", "in", self.ids)])
            requests_by_purchase = {
                request.purchase_id.id: request
                for request in purchase_requests
                if request.purchase_id
            }

        origins = [origin for origin in self.mapped("origin") if origin]
        requests_by_name = {}
        if origins:
            requests_by_name = {
                request.name: request
                for request in self.env["mer.purchase.request"].sudo().search([("name", "in", origins)])
            }

        for order in self:
            order.mer_request_id = requests_by_purchase.get(order.id) or requests_by_name.get(order.origin)

    @api.depends(
        "picking_ids.state",
        "picking_ids.wm_qc_status",
        "picking_ids.picking_type_code",
        "picking_ids.picking_type_id.warehouse_id",
    )
    def _compute_wm_store_receipt_status(self):
        for order in self:
            receipt_pickings = order.picking_ids.filtered(
                lambda picking: picking.state != "cancel" and picking.picking_type_code == "incoming"
            )
            store_receipts = receipt_pickings.filtered(
                lambda picking: picking.picking_type_id.warehouse_id
                and getattr(picking.picking_type_id.warehouse_id, "mis_role", False) == "store"
            )
            relevant_pickings = store_receipts or receipt_pickings

            if not relevant_pickings:
                order.wm_store_receipt_status = "no_receipt"
            elif relevant_pickings.filtered(lambda picking: picking.state == "done"):
                order.wm_store_receipt_status = "received"
            elif relevant_pickings.filtered(lambda picking: picking.wm_qc_status == "rejected"):
                order.wm_store_receipt_status = "defective"
            else:
                order.wm_store_receipt_status = "pending_qc"
