from odoo import _, fields, models
from odoo.exceptions import UserError


class MerDiscrepancyReport(models.Model):
    _inherit = "mer.discrepancy.report"

    picking_id = fields.Many2one(
        "stock.picking",
        string="Phiếu kho",
        tracking=True,
    )
    mer_request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yeu cau Merchandise",
        related="picking_id.mer_request_id",
        store=True,
        readonly=True,
    )
    replenishment_request_id = fields.Many2one(
        "mer.purchase.request",
        string="PR bù hàng",
        readonly=True,
        copy=False,
        tracking=True,
    )
    submitted_to_merchandise = fields.Boolean(
        string="Đã gửi Merchandise",
        default=False,
        copy=False,
        tracking=True,
    )
    source_route_type = fields.Selection(
        related="picking_id.store_route_type",
        string="Nguồn phát sinh",
        store=True,
        readonly=True,
    )
    source_route_label = fields.Char(
        related="picking_id.store_route_label",
        string="Luồng hàng",
        store=True,
        readonly=True,
    )
    handling_status = fields.Char(
        string="Tình trạng xử lý",
        compute="_compute_handling_status",
    )

    reason = fields.Selection(
        selection_add=[("damaged", "Hàng lỗi")],
        ondelete={"damaged": "cascade"},
    )

    def _compute_handling_status(self):
        for report in self:
            if report.reason == "shortage":
                if report.replenishment_request_id:
                    report.handling_status = _("Đã tạo PR bù")
                elif report.submitted_to_merchandise:
                    report.handling_status = _("Chờ Mer tạo PR bù")
                else:
                    report.handling_status = _("Chờ gửi Mer")
            elif report.reason == "damaged":
                if report.return_picking_id and report.return_picking_id.state == "done":
                    report.handling_status = _("Kho tổng đã nhận hàng lỗi")
                elif report.return_picking_id:
                    report.handling_status = _("Chờ Kho tổng nhận hàng lỗi")
                else:
                    report.handling_status = _("Chờ xử lý hàng lỗi")
            else:
                report.handling_status = _("Đang xử lý")

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Chỉ báo cáo ở trạng thái nháp mới được gửi Merchandise."))
        if self.submitted_to_merchandise:
            raise UserError(_("Báo cáo này đã được gửi Merchandise."))

        # Tự động quét và điền PO gốc từ phiếu kho hoặc PR liên quan
        if not self.purchase_id:
            if self.picking_id.purchase_id:
                self.purchase_id = self.picking_id.purchase_id
            elif self.mer_request_id:
                # Tìm PO của chính sản phẩm bị sai lệch
                po = self.mer_request_id.line_ids.filtered(lambda l: l.product_id == self.product_id).mapped('purchase_order_id')
                if not po:
                    # Nếu không xác định được đích danh, lấy PO đầu tiên của PR
                    po = self.mer_request_id.line_ids.mapped('purchase_order_id')
                
                if po:
                    self.purchase_id = po[0]

        self.write({"submitted_to_merchandise": True})
        self.message_post(
            body=_("Cửa hàng đã gửi báo cáo sai lệch cho bộ phận Merchandise."),
            subtype_xmlid="mail.mt_note",
        )
        return True

    def action_create_replenishment_po(self):
        store_shortage_reports = self.filtered(
            lambda report: report.reason == "shortage"
            and (
                report.submitted_to_merchandise
                or report.picking_id
                or report.warehouse_id.mis_role == "store"
            )
        )
        if store_shortage_reports:
            raise UserError(
                _(
                    "Báo cáo nhận thiếu hàng của Cửa hàng phải tạo PR bù hàng và đi qua luồng duyệt Merchandise trước khi tạo PO."
                )
            )
        return super().action_create_replenishment_po()

    def action_create_replenishment_pr(self):
        self.ensure_one()
        if not self.env.user.has_group("merchandise_management.group_merchandise_user"):
            raise UserError(_("Chỉ bộ phận Merchandise mới được tạo PR bù hàng."))
        if self.state != "draft":
            raise UserError(_("Chỉ báo cáo đang ở trạng thái nháp mới được tạo PR bù hàng."))
        if not self.submitted_to_merchandise:
            raise UserError(_("Báo cáo cần được Cửa hàng gửi Merchandise trước khi tạo PR bù hàng."))
        if self.reason not in ("shortage", "damaged"):
            raise UserError(_("Chỉ có thể tạo PR bù hàng cho báo cáo thiếu hàng hoặc hàng lỗi."))
        if self.replenishment_request_id:
            raise UserError(_("Báo cáo này đã tạo PR bù hàng trước đó."))

        # Xác định số lượng cần bù: Luôn lấy giá trị chênh lệch (số lượng chưa vào kho)
        # Ví dụ: Đặt 200, lỗi 1 -> Từ chối cả 200 -> Cần bù 200 (abs(difference_qty))
        qty_to_order = abs(self.difference_qty)

        if qty_to_order <= 0:
            raise UserError(_("Số lượng cần bù phải lớn hơn 0."))

        store = self.picking_id.store_receiving_store_id or self.picking_id.location_dest_id.warehouse_id.store_record_id
        warehouse = self.warehouse_id or (store.warehouse_id if store else False)
        if not warehouse:
            raise UserError(_("Không xác định được kho cửa hàng để tạo PR bù hàng."))

        request_vals = {
            "store_id": store.id if store else False,
            "warehouse_id": warehouse.id,
            "state": "submitted",
            "is_replenishment_from_discrepancy": True,
            "source_discrepancy_report_id": self.id,
            "notes": _(
                "PR bù hàng được tạo từ báo cáo thiếu hàng %(report)s, phiếu kho %(picking)s."
            )
            % {
                "report": self.name,
                "picking": self.picking_id.name or "",
            },
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product_id.id,
                        "product_qty": qty_to_order,
                        "approved_qty": qty_to_order,
                        "price_unit": self.product_id.standard_price,
                    },
                )
            ],
        }
        request = self.env["mer.purchase.request"].with_context(
            allow_discrepancy_replenishment=True
        ).create(request_vals)
        self.write(
            {
                "replenishment_request_id": request.id,
                "solution_notes": _(
                    "Đã tạo PR bù hàng %(request)s cho số lượng %(reason)s (%(qty)s cái). PR cần đi qua luồng duyệt Merchandise trước khi tạo PO."
                )
                % {
                    "request": request.name,
                    "reason": _("thiếu") if self.reason == "shortage" else _("lỗi"),
                    "qty": qty_to_order,
                },
            }
        )
        self.message_post(
            body=_("Merchandise đã tạo PR bù hàng %s từ báo cáo thiếu hàng này.") % request.name,
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Đã tạo PR bù hàng"),
                "message": _(
                    "Đã tạo %(request)s. Bạn vẫn đang ở báo cáo thiếu hàng; có thể bấm link PR bù hàng để mở PR khi cần."
                )
                % {"request": request.name},
                "sticky": False,
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
