import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MerDiscrepancyReport(models.Model):
    _inherit = "mer.discrepancy.report"

    @staticmethod
    def _extract_request_names_from_text(*texts):
        request_names = set()
        for text in texts:
            if not text:
                continue
            request_names.update(re.findall(r"PR/\d+", text))
        return list(request_names)

    def _get_related_origin_requests(self):
        request_lines = self.env["mer.purchase.request.line"]
        related_requests = self.env["mer.purchase.request"]
        request_model = self.env["mer.purchase.request"]

        for report in self.filtered(lambda current: current.picking_id and current.product_id):
            related_requests |= report.mer_request_id

            request_names = self._extract_request_names_from_text(
                report.picking_id.origin,
                report.picking_id.purchase_id.origin if report.picking_id.purchase_id else False,
            )
            if request_names:
                related_requests |= request_model.search([("name", "in", request_names)])

            related_requests |= request_lines.search(
                [
                    ("store_receipt_picking_id", "=", report.picking_id.id),
                    ("product_id", "=", report.product_id.id),
                ]
            ).mapped("request_id")

            if report.picking_id.purchase_id:
                related_requests |= request_lines.search(
                    [
                        ("purchase_order_id", "=", report.picking_id.purchase_id.id),
                        ("product_id", "=", report.product_id.id),
                        ("fulfillment_method", "=", "supplier_central"),
                    ]
                ).mapped("request_id")

        return related_requests

    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute(
            """
            UPDATE mer_discrepancy_report report
               SET state = 'done'
             WHERE report.reason = 'damaged'
               AND report.replenishment_request_id IS NOT NULL
               AND report.state = 'draft'
            """
        )
        self.env.cr.execute(
            """
            UPDATE mer_purchase_request_line line
               SET internal_flow_state = 'rejected'
              FROM mer_discrepancy_report report
             WHERE report.reason = 'damaged'
               AND report.replenishment_request_id IS NOT NULL
               AND report.state != 'cancel'
               AND report.picking_id = line.store_receipt_picking_id
               AND report.product_id = line.product_id
               AND line.internal_flow_state = 'waiting_store_receipt'
            """
        )
        return res

    picking_id = fields.Many2one(
        "stock.picking",
        string="Phiếu kho",
        tracking=True,
    )
    mer_request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yêu cầu PR",
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
    display_destination_name = fields.Char(
        string="Điểm nhận",
        compute="_compute_display_destination_name",
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

    @api.depends(
        "source_route_type",
        "warehouse_id",
        "picking_id",
        "picking_id.origin",
        "picking_id.purchase_id",
        "picking_id.purchase_id.origin",
        "mer_request_id",
        "mer_request_id.store_id",
        "replenishment_request_id",
        "replenishment_request_id.store_id",
    )
    def _compute_display_destination_name(self):
        for report in self:
            related_requests = report._get_related_origin_requests()
            origin_store = (
                report.mer_request_id.store_id
                if report.mer_request_id and report.mer_request_id.store_id
                else (
                    related_requests.filtered("store_id")[:1].store_id
                    or report.replenishment_request_id.store_id
                )
            )
            if origin_store:
                report.display_destination_name = origin_store.display_name
            elif report.source_route_type == "supplier_to_central":
                report.display_destination_name = _("Kho tổng")
            else:
                report.display_destination_name = report.warehouse_id.display_name if report.warehouse_id else False

    def _mark_origin_request_lines_resolved(self):
        request_lines = self.env["mer.purchase.request.line"]
        related_requests = self._get_related_origin_requests()
        for report in self.filtered(
            lambda current: current.reason == "damaged"
            and current.replenishment_request_id
            and current.picking_id
            and current.product_id
        ):
            request_lines |= self.env["mer.purchase.request.line"].search(
                [
                    ("store_receipt_picking_id", "=", report.picking_id.id),
                    ("product_id", "=", report.product_id.id),
                ]
            )

        if request_lines:
            request_lines.filtered(
                lambda line: line.internal_flow_state == "waiting_store_receipt"
            ).write({"internal_flow_state": "rejected"})
            related_requests |= request_lines.mapped("request_id")

        if related_requests:
            related_requests._sync_state_with_logistics()
            related_requests._compute_internal_flow_metrics()
            related_requests.mapped("line_ids")._compute_route_status_display()

    def _compute_handling_status(self):
        for report in self:
            if report.state == "done":
                report.handling_status = _("Hoàn tất")
                continue
            if report.reason == "shortage":
                if report.replenishment_request_id:
                    report.handling_status = _("Đã tạo PR bù")
                elif report.submitted_to_merchandise:
                    report.handling_status = _("Chờ Merchandise tạo đơn PR bù hàng")
                else:
                    report.handling_status = _("Chờ Cửa hàng gửi Merchandise")
            elif report.state == "done":
                report.handling_status = _("Đã xử lý")
            elif report.reason == "overage":
                if report.return_picking_id and report.return_picking_id.state == "done":
                    report.handling_status = _("Đã xử lý xong")
                elif report.return_picking_id:
                    report.handling_status = _("Chờ thu hồi hàng dư")
                elif report.submitted_to_merchandise:
                    report.handling_status = _("Chờ Merchandise xử lý")
                else:
                    report.handling_status = _("Chờ Cửa hàng gửi Mer")
            else:
                report.handling_status = _("Đang xử lý")

    def _mark_done_if_resolved(self):
        for report in self.filtered(lambda current: current.state == "draft"):
            if report.reason == "shortage" and report.replenishment_request_id:
                report.write({"state": "done"})
            elif (
                report.reason == "damaged"
                and report.replenishment_request_id
                and (
                    not report.return_picking_id
                    or report.return_picking_id.state in ("done", "cancel")
                )
            ):
                report.write({"state": "done"})

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

        self.write({"submitted_to_merchandise": True, "state": "reported"})
        related_requests = self._get_related_origin_requests()
        if related_requests:
            related_requests._sync_state_with_logistics()
            related_requests._compute_internal_flow_metrics()
            related_requests.mapped("line_ids")._compute_route_status_display()
        self.message_post(
            body=_("Cửa hàng đã gửi báo cáo sai lệch cho bộ phận Merchandise."),
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Đã gửi Merchandise"),
                "message": _(
                    "Báo cáo %(report)s đã được gửi Merchandise. Bộ phận Merchandise có thể tạo PR bù hàng khi cần."
                )
                % {"report": self.name},
                "sticky": False,
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

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

        related_requests = self._get_related_origin_requests()
        origin_request = self.mer_request_id or related_requests.filtered("store_id")[:1]
        store = (
            origin_request.store_id
            or self.picking_id.store_receiving_store_id
            or self.picking_id.location_dest_id.warehouse_id.store_record_id
        )
        warehouse = (
            origin_request.warehouse_id
            or self.warehouse_id
            or (store.warehouse_id if store else False)
        )
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
        self._mark_done_if_resolved()
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
