from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


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

    store_ready_for_receipt = fields.Boolean(
        string="Store Ready For Receipt",
        compute="_compute_store_ready_for_receipt",
        compute_sudo=True,
        store=True,
    )
    store_is_receipt_from_central = fields.Boolean(
        string="Store Receipt From Central",
        compute="_compute_store_delivery_visibility",
        compute_sudo=True,
        store=True,
    )
    store_show_in_pending_delivery = fields.Boolean(
        string="Show In Pending Delivery",
        compute="_compute_store_delivery_visibility",
        compute_sudo=True,
        store=True,
    )
    store_show_in_completed_delivery = fields.Boolean(
        string="Show In Completed Delivery",
        compute="_compute_store_delivery_visibility",
        compute_sudo=True,
        store=True,
    )
    store_actual_check_done = fields.Boolean(
        string="Da kiem hang thuc te",
        default=False,
        copy=False,
        tracking=True,
    )
    store_receipt_can_start_qc = fields.Boolean(
        string="Store Receipt Can Start QC",
        compute="_compute_store_receipt_can_start_qc",
        compute_sudo=True,
        store=True,
    )

    wm_qc_status = fields.Selection(
        [
            ("draft", "Chờ nhận hàng"),
            ("checking", "Đang kiểm tra"),
            ("passed", "Đạt"),
            ("rejected", "Hàng lỗi"),
        ],
        string="Trạng thái QC",
        default="draft",
        copy=False,
        tracking=True,
    )

    def _is_store_receipt_for_qc(self):
        self.ensure_one()
        return (
            self.picking_type_code == "incoming"
            and self.picking_type_id.warehouse_id
            and self.picking_type_id.warehouse_id.mis_role == "store"
        )

    def _is_qc_managed_receipt(self):
        self.ensure_one()
        return self._is_store_receipt_for_qc() or self._is_central_supplier_receipt()

    def _is_central_to_store_transfer(self):
        self.ensure_one()
        source_warehouse = self.location_id.warehouse_id or self.picking_type_id.warehouse_id
        destination_warehouse = (
            self.location_dest_id.warehouse_id
            or (self.mer_request_id.store_id.warehouse_id if self.mer_request_id and self.mer_request_id.store_id else False)
        )
        return bool(
            self.picking_type_code in ("internal", "outgoing")
            and source_warehouse
            and source_warehouse.mis_role == "central"
            and destination_warehouse
            and destination_warehouse.mis_role == "store"
        )

    def _is_store_receipt_from_central(self):
        self.ensure_one()
        if not self._is_store_receipt_for_qc():
            return False
        origin_pickings = self.move_ids.mapped("move_orig_ids.picking_id")
        return bool(origin_pickings.filtered(lambda picking: picking._is_central_to_store_transfer()))

    @api.depends("picking_type_code", "location_dest_id", "location_dest_id.warehouse_id", "picking_type_id.warehouse_id")
    def _compute_wm_is_incoming_receipt(self):
        for picking in self:
            picking.wm_is_incoming_receipt = picking._is_qc_managed_receipt()

    @api.depends(
        "state",
        "picking_type_code",
        "picking_type_id.warehouse_id",
        "move_ids.state",
        "move_ids.move_orig_ids.state",
        "move_ids.move_orig_ids.picking_id.state",
    )
    def _compute_store_ready_for_receipt(self):
        for picking in self:
            if not picking._is_store_receipt_for_qc() or picking.state in ("done", "cancel"):
                picking.store_ready_for_receipt = False
                continue

            origin_moves = picking.move_ids.mapped("move_orig_ids")
            if not origin_moves:
                picking.store_ready_for_receipt = True
                continue

            picking.store_ready_for_receipt = all(
                move.state == "done" or move.picking_id.state == "done"
                for move in origin_moves
            )

    @api.depends(
        "state",
        "picking_type_code",
        "location_id.warehouse_id",
        "location_dest_id.warehouse_id",
        "picking_type_id.warehouse_id",
        "move_ids.move_orig_ids.picking_id.state",
        "move_ids.move_orig_ids.picking_id.location_id.warehouse_id",
        "store_ready_for_receipt",
    )
    def _compute_store_delivery_visibility(self):
        for picking in self:
            is_store_receipt_from_central = picking._is_store_receipt_from_central()
            picking.store_is_receipt_from_central = is_store_receipt_from_central
            picking.store_show_in_pending_delivery = bool(
                picking._is_central_to_store_transfer() and picking.state not in ("done", "cancel")
            )
            picking.store_show_in_completed_delivery = bool(
                picking._is_central_to_store_transfer() and picking.state == "done"
            )

    @api.depends(
        "store_actual_check_done",
        "wm_expected_qty",
        "wm_received_qty",
        "wm_qc_status",
        "state",
        "move_ids.product_uom.rounding",
    )
    def _compute_store_receipt_can_start_qc(self):
        for picking in self:
            if (
                not picking._is_store_receipt_for_qc()
                or not picking.store_actual_check_done
                or picking.wm_qc_status != "draft"
                or picking.state in ("done", "cancel")
            ):
                picking.store_receipt_can_start_qc = False
                continue

            precision = (
                picking.move_ids[:1].product_uom.rounding
                if picking.move_ids[:1].product_uom
                else 0.01
            )
            picking.store_receipt_can_start_qc = (
                float_compare(
                    picking.wm_received_qty,
                    picking.wm_expected_qty,
                    precision_rounding=precision or 0.01,
                )
                == 0
            )

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
            source_warehouse = picking.location_id.warehouse_id or picking.picking_type_id.warehouse_id

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
                destination_warehouse = (
                    picking.location_dest_id.warehouse_id
                    or (picking.mer_request_id.store_id.warehouse_id if picking.mer_request_id and picking.mer_request_id.store_id else False)
                )
                route_type = "central_to_store"
                route_label = _("Kho tổng -> Cửa hàng")
                source_party = source_warehouse.display_name if source_warehouse else _("Kho tổng")
                source_document = picking.origin or picking.name

            if destination_warehouse:
                store = store_model.search([("warehouse_id", "=", destination_warehouse.id)], limit=1)

            picking.store_receiving_store_id = store
            picking.store_route_type = route_type
            picking.store_route_label = route_label
            picking.store_source_party_display = source_party
            picking.store_source_document_ref = source_document

    def _check_wm_incoming_receipt(self):
        non_receipt = self.filtered(lambda picking: not picking._is_qc_managed_receipt())
        if non_receipt:
            raise UserError(_("Chỉ các phiếu nhập NCC cần kiểm hàng mới được thực hiện QC."))

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
                created_pickings = picking.mer_request_id._create_internal_pickings_for_lines(request_lines)
                central_pickings = created_pickings.filtered(lambda current: current._is_central_to_store_transfer())
                picking.message_post(
                    body=_(
                        "Kho tổng đã QC đạt và nhập kho. Hệ thống đã tự tạo %s phiếu giao Kho tổng -> Cửa hàng để chuyển sang danh sách Đơn cần giao."
                    )
                    % len(central_pickings)
                )

    def _get_merchandise_notification_users(self):
        manager_group = self.env.ref("merchandise_management.group_merchandise_manager", raise_if_not_found=False)
        user_group = self.env.ref("merchandise_management.group_merchandise_user", raise_if_not_found=False)
        return (manager_group.sudo().user_ids or user_group.sudo().user_ids).filtered(lambda user: user.partner_id)

    def _build_damage_details_html(self):
        self.ensure_one()
        items = []
        for move in self.move_ids.filtered(lambda current_move: current_move.state != "cancel" and current_move.wm_damaged_qty > 0):
            items.append(
                _("<li><b>%s</b>: %s hư hỏng. Ghi chú: %s</li>")
                % (
                    move.product_id.display_name,
                    move.wm_damaged_qty,
                    move.wm_damage_note or _("Tự động ghi nhận lỗi tại Kho tổng"),
                )
            )
        return "".join(items)

    def _prepare_auto_qc_rejection_from_damage(self):
        for picking in self:
            if not picking.wm_qc_note:
                picking.wm_qc_note = _("Tự động QC không đạt vì phát hiện hàng lỗi tại Kho tổng.")
            for move in picking.move_ids.filtered(lambda current_move: current_move.state != "cancel" and current_move.wm_damaged_qty > 0):
                if not move.wm_damage_note:
                    move.wm_damage_note = _("Tự động QC không đạt vì phát hiện hàng lỗi tại Kho tổng.")

    def action_complete_central_receipt_check(self):
        for picking in self:
            if not picking._is_central_supplier_receipt():
                raise UserError(_("Chỉ áp dụng thao tác này cho phiếu NCC -> Kho tổng."))
            if picking.state in ("done", "cancel"):
                continue
            if not picking.store_actual_check_done:
                raise UserError(_("Cần hoàn tất bước Kiểm hàng thực tế trước khi chốt kiểm hàng."))

            active_moves = picking.move_ids.filtered(lambda current_move: current_move.state != "cancel")
            if not active_moves:
                raise UserError(_("Phiếu không có dòng hàng hợp lệ để kiểm hàng."))

            if any(move.wm_damaged_qty > 0 for move in active_moves):
                picking._prepare_auto_qc_rejection_from_damage()
                if picking.wm_qc_status == "draft":
                    super(StockPicking, picking).action_start_qc()
                picking.action_qc_reject()
                continue

            overage_moves = active_moves.filtered(lambda move: move.quantity > move.product_uom_qty)
            if overage_moves:
                for move in overage_moves:
                    move.quantity = move.product_uom_qty
                picking.message_post(
                    body=_(
                        "Kho tổng đã chốt nhận đúng số lượng PR. Phần hàng thừa từ NCC không được nhận vào quy trình tiếp theo."
                    ),
                    subtype_xmlid="mail.mt_note",
                )

            if picking.wm_qc_status == "draft":
                super(StockPicking, picking).action_start_qc()
            picking.action_qc_pass()

        self._sync_related_mer_request_state()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.id if len(self) == 1 else False,
            "view_mode": "form" if len(self) == 1 else "list,form",
            "target": "current",
        }

    def _handle_central_supplier_qc_rejection(self):
        request_line_model = self.env["mer.purchase.request.line"]
        todo_activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        merch_users = self._get_merchandise_notification_users()
        merch_partners = merch_users.mapped("partner_id").ids

        for picking in self.filtered(lambda receipt: receipt._is_central_supplier_receipt() and receipt.wm_qc_status == "rejected"):
            request_lines = request_line_model.search(
                [
                    ("request_id", "=", picking.mer_request_id.id),
                    ("purchase_order_id", "=", picking.purchase_id.id),
                    ("fulfillment_method", "=", "supplier_central"),
                ]
            )
            if request_lines:
                request_lines.with_context(store_skip_sync_rule=True).write(
                    {
                        "purchase_order_id": False,
                        "internal_picking_id": False,
                        "store_receipt_picking_id": False,
                        "internal_flow_state": "not_applicable",
                    }
                )

            request = picking.mer_request_id
            if not request:
                continue

            if merch_partners:
                request.message_subscribe(partner_ids=merch_partners)

            body = _(
                "<b>Kho tổng QC không đạt.</b><br/>"
                "Phiếu <b>%s</b> từ NCC <b>%s</b> đã bị từ chối vì có hàng lỗi.<br/>"
                "<b>Chi tiết lỗi:</b><ul>%s</ul>"
                "Các dòng PR liên quan đã được mở lại để Merchandise tự tạo PO mới."
            ) % (
                picking.name,
                picking.partner_id.display_name or _("Nhà cung cấp"),
                picking._build_damage_details_html() or _("<li>Đã phát hiện lỗi trên lô hàng.</li>"),
            )
            request.message_post(
                body=body,
                partner_ids=merch_partners,
                subtype_xmlid="mail.mt_comment",
                subject=_("Kho tổng QC không đạt - cần tạo lại PO: %s") % picking.name,
            )
            picking.message_post(
                body=_("Đã gửi thông báo cho Merchandise để tự tạo lại PO mới cho PR liên quan."),
                subtype_xmlid="mail.mt_note",
            )

            if todo_activity_type:
                for user in merch_users:
                    request.activity_schedule(
                        todo_activity_type.id,
                        user_id=user.id,
                        note=_("Phiếu %s QC không đạt tại Kho tổng. Vui lòng tạo lại PO mới cho PR %s.") % (
                            picking.name,
                            request.name,
                        ),
                    )

    def _sync_related_mer_request_state(self):
        requests = (self.mapped("mer_request_id") | self.mapped("move_ids.picking_id.mer_request_id")).filtered(bool)
        request_lines = self.env["mer.purchase.request.line"].search([
            "|", ("internal_picking_id", "in", self.ids), 
                 ("store_receipt_picking_id", "in", self.ids)
        ])
        requests |= request_lines.mapped("request_id").filtered(bool)
        if requests:
            requests._sync_state_with_logistics()

    def action_start_store_delivery(self):
        for picking in self:
            if not picking._is_central_to_store_transfer():
                raise UserError(_("Ch\u1ec9 \u00e1p d\u1ee5ng thao t\u00e1c n\u00e0y cho phi\u1ebfu giao t\u1eeb Kho t\u1ed5ng \u0111\u1ebfn C\u1eeda h\u00e0ng."))
            if picking.state in ("done", "cancel"):
                continue

            if picking.state == "draft":
                picking.action_confirm()
            if picking.state in ("confirmed", "waiting"):
                picking.action_assign()

            for move in picking.move_ids.filtered(lambda current_move: current_move.state != "cancel"):
                if not move.quantity:
                    move.quantity = move.product_uom_qty

            picking.with_context(skip_immediate=True).button_validate()

        self._sync_related_mer_request_state()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.id if len(self) == 1 else False,
            "view_mode": "form" if len(self) == 1 else "list,form",
            "target": "current",
        }

    def action_view_store_discrepancy_reports(self):
        self.ensure_one()
        reports = self.env["mer.discrepancy.report"].search([("picking_id", "=", self.id)])
        action = self.env["ir.actions.actions"]._for_xml_id(
            "merchandise_management.action_mer_discrepancy_report"
        )
        action["domain"] = [("picking_id", "=", self.id)]
        if len(reports) == 1:
            action.update(
                {
                    "res_id": reports.id,
                    "view_mode": "form",
                    "views": [(False, "form")],
                }
            )
        return action

    def action_qc_pass(self):
        auto_reject_pickings = self.filtered(
            lambda picking: picking._is_central_supplier_receipt()
            and picking.wm_qc_status == "checking"
            and any(move.wm_damaged_qty > 0 for move in picking.move_ids.filtered(lambda current_move: current_move.state != "cancel"))
        )
        if auto_reject_pickings:
            auto_reject_pickings._prepare_auto_qc_rejection_from_damage()
            auto_reject_pickings.action_qc_reject()

        remaining_pickings = self - auto_reject_pickings
        result = False
        if remaining_pickings:
            result = super(StockPicking, remaining_pickings).action_qc_pass()

        pickings_to_validate = remaining_pickings.filtered(
            lambda picking: picking._is_store_receipt_for_qc() and picking.state not in ("done", "cancel")
        )
        if pickings_to_validate:
            validate_result = pickings_to_validate.button_validate()
            self._sync_related_mer_request_state()
            return validate_result or result
        self._sync_related_mer_request_state()
        return result

    def action_start_qc(self):
        blocked_pickings = self.filtered(
            lambda picking: picking._is_store_receipt_for_qc() and not picking.store_receipt_can_start_qc
        )
        if blocked_pickings:
            raise UserError(
                _("Phai kiem hang thuc te du so luong truoc khi bat dau QC.")
            )
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
        rejected_store_pickings = self.filtered(
            lambda picking: picking._is_store_receipt_for_qc() and picking.wm_qc_status == "rejected"
        )
        if rejected_store_pickings:
            request_lines = self.env["mer.purchase.request.line"].search(
                [("store_receipt_picking_id", "in", rejected_store_pickings.ids)]
            )
            request_lines.write({"internal_flow_state": "rejected"})

            for picking in rejected_store_pickings:
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
        self._handle_central_supplier_qc_rejection()
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
                "mer_request_id": picking.mer_request_id.id,
                "partner_id": picking.location_id.warehouse_id.partner_id.id if picking.location_id.warehouse_id.partner_id else False,
                "picking_type_id": store_warehouse.in_type_id.id,
                "location_id": transit_location.id,
                "location_dest_id": store_warehouse.lot_stock_id.id,
                "origin": (picking.origin or picking.name) + _(" - Giao hàng"),
                "scheduled_date": picking.scheduled_date,
                "move_ids": [
                    (0, 0, {
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
            lambda picking: picking._is_qc_managed_receipt() and picking.state not in ("done", "cancel")
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
            request_line_model = self.env["mer.purchase.request.line"]

            delivered_central_pickings = completed_pickings.filtered(lambda picking: picking._is_central_to_store_transfer())
            if delivered_central_pickings:
                delivery_lines = request_line_model.search([("internal_picking_id", "in", delivered_central_pickings.ids)])
                waiting_store_receipt_lines = delivery_lines.filtered("store_receipt_picking_id")
                direct_delivery_lines = delivery_lines - waiting_store_receipt_lines
                if waiting_store_receipt_lines:
                    waiting_store_receipt_lines.write({"internal_flow_state": "waiting_store_receipt"})
                if direct_delivery_lines:
                    direct_delivery_lines.write({"internal_flow_state": "delivered"})

            completed_store_receipts = completed_pickings.filtered(
                lambda picking: picking._is_store_receipt_for_qc() and picking._is_store_receipt_from_central()
            )
            if completed_store_receipts:
                request_line_model.search(
                    [("store_receipt_picking_id", "in", completed_store_receipts.ids)]
                ).write({"internal_flow_state": "delivered"})
        self._sync_related_mer_request_state()
        return result
