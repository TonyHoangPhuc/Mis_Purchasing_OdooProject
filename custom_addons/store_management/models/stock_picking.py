from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    store_receiving_store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng nhận",
        compute="_compute_store_receiving_context",
        compute_sudo=True,
        store=True,
    )
    store_route_type = fields.Selection(
        [
            ("supplier_to_central", "NCC -> Kho tổng"),
            ("supplier_to_store", "NCC -> Cửa hàng"),
            ("central_to_store", "Kho tổng -> Cửa hàng"),
        ],
        string="Loại tuyến hàng",
        compute="_compute_store_receiving_context",
        compute_sudo=True,
        store=True,
    )
    store_route_label = fields.Char(
        string="Nguồn hàng",
        compute="_compute_store_receiving_context",
        compute_sudo=True,
        store=True,
    )
    store_source_party_display = fields.Char(
        string="Nguồn giao",
        compute="_compute_store_receiving_context",
        compute_sudo=True,
        store=True,
    )
    store_source_document_ref = fields.Char(
        string="Chứng từ nguồn",
        compute="_compute_store_receiving_context",
        compute_sudo=True,
        store=True,
    )

    def _is_store_receipt_for_qc(self):
        self.ensure_one()
        return (
            self.picking_type_code == "incoming"
            and self.picking_type_id.warehouse_id
            and self.picking_type_id.warehouse_id.mis_role == "store"
        )

    def _is_central_to_store_transfer(self):
        self.ensure_one()
        return bool(
            self.picking_type_code == "internal"
            and self.location_id.warehouse_id
            and self.location_id.warehouse_id.mis_role == "central"
            and self.location_dest_id.warehouse_id
            and self.location_dest_id.warehouse_id.mis_role == "store"
        )

    @api.depends("picking_type_code", "location_dest_id", "location_dest_id.warehouse_id", "picking_type_id.warehouse_id")
    def _compute_wm_is_incoming_receipt(self):
        for picking in self:
            picking.wm_is_incoming_receipt = picking._is_store_receipt_for_qc()

    @api.depends(
        "picking_type_code",
        "picking_type_id.warehouse_id",
        "location_id.warehouse_id",
        "location_dest_id.warehouse_id",
        "partner_id",
        "purchase_id",
        "origin",
        "name",
    )
    def _compute_store_receiving_context(self):
        store_model = self.env["store.store"].sudo()
        for picking in self:
            store = False
            route_type = False
            route_label = False
            source_party = False
            source_document = False
            destination_warehouse = False

            if (
                picking.picking_type_code == "incoming"
                and picking.picking_type_id.warehouse_id
                and picking.picking_type_id.warehouse_id.mis_role == "central"
                and picking.mer_request_id
                and picking.mer_request_id.store_id
            ):
                store = picking.mer_request_id.store_id
                route_type = "supplier_to_central"
                route_label = _("NCC -> Kho tổng")
                source_party = picking.partner_id.display_name or _("Nhà cung cấp")
                source_document = picking.purchase_id.name or picking.origin or picking.name
            elif (
                picking.picking_type_code == "incoming"
                and picking.picking_type_id.warehouse_id
                and picking.picking_type_id.warehouse_id.mis_role == "store"
            ):
                destination_warehouse = picking.picking_type_id.warehouse_id
                route_type = "supplier_to_store"
                route_label = _("NCC -> Cửa hàng")
                source_party = picking.partner_id.display_name or _("Nhà cung cấp")
                source_document = picking.purchase_id.name or picking.origin or picking.name
            elif picking._is_central_to_store_transfer():
                destination_warehouse = picking.location_dest_id.warehouse_id
                route_type = "central_to_store"
                route_label = _("Kho tổng -> Cửa hàng")
                source_party = picking.location_id.warehouse_id.display_name or _("Kho tổng")
                source_document = picking.origin or picking.name

            if destination_warehouse:
                store = store_model.search([("warehouse_id", "=", destination_warehouse.id)], limit=1)

            picking.store_receiving_store_id = store
            picking.store_route_type = route_type
            picking.store_route_label = route_label
            picking.store_source_party_display = source_party
            picking.store_source_document_ref = source_document

    def _check_wm_incoming_receipt(self):
        non_receipt = self.filtered(lambda picking: not picking._is_store_receipt_for_qc())
        if non_receipt:
            raise UserError(_("Chỉ phiếu nhập từ NCC vào kho cửa hàng mới được thực hiện QC."))

    def _is_central_supplier_receipt(self):
        self.ensure_one()
        return bool(
            self.picking_type_code == "incoming"
            and self.picking_type_id.warehouse_id
            and self.picking_type_id.warehouse_id.mis_role == "central"
            and self.purchase_id
            and self.mer_request_id
        )

    def _mark_central_receipts_ready_for_delivery_check(self):
        request_line_model = self.env["mer.purchase.request.line"]
        for picking in self.filtered(lambda receipt: receipt._is_central_supplier_receipt() and receipt.state == "done"):
            request_lines = request_line_model.search(
                [
                    ("request_id", "=", picking.mer_request_id.id),
                    ("purchase_order_id", "=", picking.purchase_id.id),
                    ("fulfillment_method", "=", "supplier_central"),
                    ("internal_picking_id", "=", False),
                ]
            )
            if request_lines:
                request_lines.with_context(store_skip_sync_rule=True).write({"internal_flow_state": "pending_check"})
                picking.message_post(
                    body=_(
                        "Kho tổng đã QC đạt và nhập kho. Các dòng PR liên quan đã chuyển sang bước kiểm hàng để giao cửa hàng."
                    )
                )

    def _sync_related_mer_request_state(self):
        requests = (self.mapped("mer_request_id") | self.mapped("move_ids.picking_id.mer_request_id")).filtered(bool)
        if requests:
            requests._sync_state_with_logistics()

    def action_qc_pass(self):
        result = super().action_qc_pass()
        pickings_to_validate = self.filtered(
            lambda picking: picking._is_store_receipt_for_qc() and picking.state not in ("done", "cancel")
        )
        if pickings_to_validate:
            validate_result = pickings_to_validate.button_validate()
            self._sync_related_mer_request_state()
            return validate_result or result
        self._sync_related_mer_request_state()
        return result

    def action_start_qc(self):
        result = super().action_start_qc()
        for picking in self.filtered(lambda current: current._is_store_receipt_for_qc()):
            if picking.wm_damaged_qty > 0:
                picking.message_post(
                    body=_(
                        "Cảnh báo: phát hiện %s sản phẩm hư hỏng. Nếu xác nhận QC không đạt, "
                        "phiếu sẽ dừng theo đúng luồng giao nhận để không làm sai tồn kho."
                    )
                    % picking.wm_damaged_qty
                )
        return result

    def action_qc_reject(self):
        result = super().action_qc_reject()
        rejected_pickings = self.filtered(
            lambda picking: picking._is_store_receipt_for_qc() and picking.wm_qc_status == "rejected"
        )
        if rejected_pickings:
            request_lines = self.env["mer.purchase.request.line"].search(
                [("internal_picking_id", "in", rejected_pickings.ids)]
            )
            request_lines.write({"internal_flow_state": "rejected"})

            for picking in rejected_pickings:
                request = picking.mer_request_id
                if not request:
                    continue

                damaged_details = ""
                for move in picking.move_ids.filtered(lambda current_move: current_move.state != "cancel"):
                    qty_damaged = move.wm_damaged_qty or move.quantity
                    damaged_details += _("<li><b>%s</b>: %s cái hư hỏng. Ghi chú: %s</li>") % (
                        move.product_id.display_name,
                        qty_damaged,
                        move.wm_damage_note or _("Đang cập nhật"),
                    )

                request.message_post(
                    body=_(
                        "<b>Lô hàng lỗi!</b><br/>"
                        "Phiếu <b>%s</b> tại <b>%s</b> đã QC không đạt.<br/>"
                        "<b>Sản phẩm bị lỗi:</b><ul>%s</ul>"
                        "Phiếu giao nhận đã được dừng theo trạng thái QC hiện tại. "
                        "Vui lòng kiểm tra và xử lý lại đơn hàng."
                    )
                    % (
                        picking.name,
                        picking.store_receiving_store_id.name or picking.picking_type_id.warehouse_id.display_name,
                        damaged_details,
                    ),
                    subject=_("Lô hàng lỗi - QC không đạt: %s") % picking.name,
                )
        self._sync_related_mer_request_state()
        return result

    def action_confirm(self):
        # Tự động tách luồng 1 bước thành 2 bước (Transit) khi user tạo điều chuyển trực tiếp từ Kho tổng sang Cửa hàng
        transit_location = self.env.company.internal_transit_location_id or self.env.ref('stock.stock_location_inter_company', raise_if_not_found=False)
        central_to_store_pickings = self.filtered(
            lambda p: p.picking_type_code in ("internal", "outgoing")
            and p.location_id.warehouse_id
            and p.location_id.warehouse_id.mis_role == "central"
            and p.location_dest_id.warehouse_id
            and p.location_dest_id.warehouse_id.mis_role == "store"
            and not p._context.get("skip_transit_interception")
        )

        store_receipts = {}
        for picking in central_to_store_pickings:
            if not transit_location:
                continue
            store_warehouse = picking.location_dest_id.warehouse_id
            
            # 1. Đổi đích của phiếu hiện tại thành Transit
            picking.location_dest_id = transit_location.id
            for move in picking.move_ids:
                move.location_dest_id = transit_location.id

            # 2. Tạo phiếu nhận hàng tương ứng cho Cửa hàng
            store_picking = self.env["stock.picking"].with_context(skip_transit_interception=True).sudo().create({
                "partner_id": picking.location_id.warehouse_id.partner_id.id if picking.location_id.warehouse_id.partner_id else False,
                "picking_type_id": store_warehouse.in_type_id.id,
                "location_id": transit_location.id,
                "location_dest_id": store_warehouse.lot_stock_id.id,
                "origin": (picking.origin or picking.name) + _(" - Giao hàng"),
                "scheduled_date": picking.scheduled_date,
                "move_ids": [
                    (0, 0, {
                        "name": move.product_id.display_name,
                        "description_picking": move.product_id.display_name,
                        "product_id": move.product_id.id,
                        "product_uom_qty": move.product_uom_qty,
                        "product_uom": move.product_uom.id,
                        "location_id": transit_location.id,
                        "location_dest_id": store_warehouse.lot_stock_id.id,
                    })
                    for move in picking.move_ids if move.product_uom_qty > 0
                ],
            })
            store_receipts[picking.id] = store_picking

        result = super().action_confirm()

        # 3. Liên kết move để phiếu nhận hàng chỉ Sẵn sàng khi phiếu giao hoàn tất
        for picking_id, store_picking in store_receipts.items():
            central_picking = self.browse(picking_id)
            for store_move in store_picking.move_ids:
                central_move = central_picking.move_ids.filtered(lambda m: m.product_id == store_move.product_id)
                if central_move:
                    store_move.move_orig_ids = [(6, 0, central_move.ids)]
            store_picking.action_confirm()

        return result

    def button_validate(self):
        pickings_requiring_qc = self.filtered(
            lambda picking: picking._is_store_receipt_for_qc() and picking.state not in ("done", "cancel")
        )
        blocking_pickings = pickings_requiring_qc.filtered(lambda picking: picking.wm_qc_status != "passed")
        if blocking_pickings:
            raise UserError(
                _("Phiếu %s phải QC đạt trước khi xác nhận nhập kho.")
                % ", ".join(blocking_pickings.mapped("name"))
            )

        result = super().button_validate()
        completed_pickings = self.filtered(lambda picking: picking.state == "done")
        if completed_pickings:
            completed_pickings._mark_central_receipts_ready_for_delivery_check()
            request_lines = self.env["mer.purchase.request.line"].search(
                [("internal_picking_id", "in", completed_pickings.ids)]
            )
            request_lines.write({"internal_flow_state": "delivered"})
        self._sync_related_mer_request_state()
        return result
