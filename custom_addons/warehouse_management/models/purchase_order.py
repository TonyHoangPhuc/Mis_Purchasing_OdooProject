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
        store=True,
    )

    @api.depends("origin")
    def _compute_mer_request_id(self):
        origins = [origin for origin in self.mapped("origin") if origin]
        requests_by_name = {}
        if origins:
            requests_by_name = {
                request.name: request
                for request in self.env["mer.purchase.request"].sudo().search([("name", "in", origins)])
            }

        for order in self:
            order.mer_request_id = requests_by_name.get(order.origin)

    @api.depends(
        "picking_ids.state",
        "picking_ids.wm_qc_status",
        "picking_ids.picking_type_code",
        "picking_ids.picking_type_id.warehouse_id",
    )
    def _compute_wm_store_receipt_status(self):
        for order in self:
            receipt_pickings = order.picking_ids.filtered(lambda picking: picking.picking_type_code == "incoming")
            store_receipts = receipt_pickings.filtered(
                lambda picking: picking.picking_type_id.warehouse_id
                and getattr(picking.picking_type_id.warehouse_id, "mis_role", False) == "store"
            )
            relevant_pickings = store_receipts or receipt_pickings
            active_pickings = relevant_pickings.filtered(lambda picking: picking.state != "cancel")
            rejected_pickings = relevant_pickings.filtered(lambda picking: picking.wm_qc_status == "rejected")

            if not relevant_pickings:
                order.wm_store_receipt_status = "no_receipt"
            elif relevant_pickings.filtered(lambda picking: picking.state == "done"):
                order.wm_store_receipt_status = "received"
            elif rejected_pickings:
                order.wm_store_receipt_status = "defective"
            elif active_pickings:
                order.wm_store_receipt_status = "pending_qc"
            else:
                order.wm_store_receipt_status = "no_receipt"
