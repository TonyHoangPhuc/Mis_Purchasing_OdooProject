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
    wm_has_shortage_alert = fields.Boolean(
        string="Thiếu hàng từ nguồn",
        default=False,
        copy=False,
    )
    store_actual_check_done = fields.Boolean(
        string="Đã kiểm hàng thực tế",
        default=False,
        copy=False,
        tracking=True,
    )
    store_receipt_issue_type = fields.Selection(
        [
            ("none", "Không có sai lệch"),
            ("shortage", "Nhận thiếu"),
            ("overage", "Nhận dư"),
            ("mixed", "Vừa thiếu vừa dư"),
            ("damaged_rejected", "Từ chối lô do hàng lỗi"),
        ],
        string="Vấn đề nhận hàng",
        default="none",
        copy=False,
        tracking=True,
    )
    store_rejected_return_picking_id = fields.Many2one(
        "stock.picking",
        string="Phiếu trả NCC do hàng lỗi",
        readonly=True,
        copy=False,
        tracking=True,
    )
    store_receipt_can_start_qc = fields.Boolean(
        string="Có thể bắt đầu QC nhận hàng Store",
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

    def _get_store_receipt_central_source_picking(self):
        self.ensure_one()
        if not self._is_store_receipt_from_central():
            return self.env["stock.picking"]
        return self.move_ids.mapped("move_orig_ids.picking_id").filtered(
            lambda picking: picking._is_central_to_store_transfer()
        )[:1]

    def _get_store_exception_parent_location(self):
        self.ensure_one()
        return (
            self.env.company.internal_transit_location_id
            or self.env.ref("stock.stock_location_locations", raise_if_not_found=False)
            or self.location_id
        )

    def _get_or_create_store_exception_location(self, name):
        self.ensure_one()
        parent_location = self._get_store_exception_parent_location()
        location = self.env["stock.location"].sudo().search(
            [
                ("location_id", "=", parent_location.id),
                ("name", "=", name),
                ("usage", "=", "internal"),
            ],
            limit=1,
        )
        if not location:
            location = self.env["stock.location"].sudo().create(
                {
                    "name": name,
                    "location_id": parent_location.id,
                    "usage": "internal",
                    "company_id": self.company_id.id or self.env.company.id,
                }
            )
        return location

    def _get_or_create_store_excess_holding_location(self):
        self.ensure_one()
        store_name = self.store_receiving_store_id.name or self.picking_type_id.warehouse_id.display_name or _("Cửa hàng")
        return self._get_or_create_store_exception_location(_("Hàng dư chờ Kho tổng thu hồi - %s") % store_name)

    def _get_or_create_central_damaged_location(self):
        self.ensure_one()
        central_picking = self._get_store_receipt_central_source_picking()
        central_name = (
            central_picking.location_id.warehouse_id.display_name
            if central_picking and central_picking.location_id.warehouse_id
            else _("Kho tổng")
        )
        return self._get_or_create_store_exception_location(_("Hàng lỗi chờ Kho tổng xử lý - %s") % central_name)

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
        "move_ids.move_orig_ids.picking_id.location_id.warehouse_id",
        "move_ids.move_orig_ids.picking_id.location_dest_id.warehouse_id",
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
                if picking._is_store_receipt_from_central():
                    central_picking = picking._get_store_receipt_central_source_picking()
                    source_warehouse = central_picking.location_id.warehouse_id if central_picking else False
                    route_type = "central_to_store"
                    route_label = _("Kho tổng -> Cửa hàng")
                    source_party = source_warehouse.display_name if source_warehouse else _("Kho tổng")
                else:
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
            blocking_reports = self.env["mer.discrepancy.report"].search(
                [
                    ("picking_id", "=", picking.id),
                    ("reason", "=", "damaged"),
                ],
                limit=1,
            )
            if blocking_reports:
                picking.message_post(
                    body=_(
                        "Kho tổng đã nhập số lượng thực nhận nhưng có báo cáo hàng lỗi. Hệ thống không tự tạo phiếu giao về Cửa hàng để tránh giao nhầm hàng lỗi."
                    ),
                    subtype_xmlid="mail.mt_note",
                )
                continue

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
                
                # Nếu có báo cáo thiếu hàng, đánh dấu cảnh báo trên phiếu giao
                shortage_report = self.env["mer.discrepancy.report"].search([
                    ("picking_id", "=", picking.id),
                    ("reason", "=", "shortage"),
                ], limit=1)
                if shortage_report:
                    central_pickings.write({"wm_has_shortage_alert": True})
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
                raise UserError(_("Phiếu có hàng hư hỏng. Vui lòng dùng nút Trả hàng NCC để từ chối toàn bộ lô hàng lỗi."))
                continue

            issue_type = picking._ensure_store_receipt_discrepancy_reports(
                submit_shortage=True,
                shortage_note=_("Kho tổng nhận thiếu hàng từ NCC. Báo cáo đã được gửi Merchandise để xử lý tiếp."),
                create_excess_report=False,
            )
            picking.store_receipt_issue_type = issue_type
            
            # Tự động bóp PO nếu có thiếu hàng để giải phóng ngân sách
            if issue_type in ("shortage", "mixed"):
                picking._adjust_po_quantities_to_actual()

            if issue_type in ("overage", "mixed"):
                picking.message_post(
                    body=_(
                        "Kho tổng chỉ nhập đúng số lượng theo PR/PO. Phần hàng dư từ NCC không được cộng vào tồn kho."
                    ),
                    subtype_xmlid="mail.mt_note",
                )

            if issue_type in ("shortage", "mixed"):
                shortage_product_ids = active_moves.filtered(
                    lambda move: move.quantity < move.product_uom_qty
                ).mapped("product_id").ids
                request_lines = self.env["mer.purchase.request.line"].search(
                    [
                        ("request_id", "=", picking.mer_request_id.id),
                        ("purchase_order_id", "=", picking.purchase_id.id),
                        ("fulfillment_method", "=", "supplier_central"),
                        ("product_id", "in", shortage_product_ids),
                    ]
                )
                request_lines.with_context(store_skip_sync_rule=True).write(
                    {"internal_flow_state": "waiting_stock"}
                )
                picking.message_post(
                    body=_("Kho tổng nhận thiếu hàng từ NCC. Hệ thống đã tạo báo cáo thiếu hàng và gửi Merchandise."),
                    subtype_xmlid="mail.mt_note",
                )

            if picking.wm_received_qty <= 0:
                picking.write(
                    {
                        "wm_qc_status": "passed",
                        "wm_qc_checked_by": self.env.user.id,
                        "wm_qc_checked_on": fields.Datetime.now(),
                    }
                )
                picking.action_cancel()
                picking.message_post(
                    body=_("Kho tổng không có số lượng thực nhận để nhập kho. Hệ thống đã tạo báo cáo thiếu hàng và gửi Merchandise."),
                    subtype_xmlid="mail.mt_note",
                )
                continue

            if picking.wm_qc_status == "draft":
                super(StockPicking, picking).action_start_qc()
            picking.with_context(
                skip_immediate=True,
                skip_backorder=True,
                cancel_backorder=True,
                picking_ids_not_to_backorder=picking.ids,
            ).action_qc_pass()

        self._sync_related_mer_request_state()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.id if len(self) == 1 else False,
            "view_mode": "form" if len(self) == 1 else "list,form",
            "views": [(False, "form")] if len(self) == 1 else [(False, "list"), (False, "form")],
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
            picking.message_post(
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
                        "mail.mail_activity_data_todo",
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
                raise UserError(_("Chỉ áp dụng thao tác này cho phiếu giao từ Kho tổng đến Cửa hàng."))
            if picking.state in ("done", "cancel"):
                continue

            if picking.state == "draft":
                picking.action_confirm()
            if picking.state in ("confirmed", "waiting"):
                picking.action_assign()

            # Xử lý hàng lỗi (Damaged) - Nếu có hàng lỗi tại kho tổng trước khi giao
            picking._handle_damaged_goods_movement()
            
            # Ghi nhận sai lệch (Dư/Thiếu) ngay lúc xuất kho để Merchandise nắm bắt kịp thời
            picking._ensure_store_receipt_discrepancy_reports(
                submit_shortage=True,
                shortage_note=_("Kho tổng chủ động giao thiếu so với PR. Đang chờ hàng từ NCC về bù."),
                create_excess_report=True
            )

            if picking.wm_has_shortage_alert:
                picking.mer_request_id.message_post(
                    body=_("<b>Thông báo:</b> Kho tổng đã chủ động giao trước phần hàng có sẵn cho PR %s, dù NCC vẫn đang giao thiếu.") % picking.mer_request_id.name,
                    subtype_xmlid="mail.mt_comment",
                )

            # Xác nhận giao hàng thực tế
            picking.with_context(
                skip_immediate=True,
                skip_backorder=True,
                cancel_backorder=True,
                picking_ids_not_to_backorder=picking.ids,
            ).button_validate()

        self._sync_related_mer_request_state()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.id if len(self) == 1 else False,
            "view_mode": "form" if len(self) == 1 else "list,form",
            "views": [(False, "form")] if len(self) == 1 else [(False, "list"), (False, "form")],
            "target": "current",
        }

    def _handle_damaged_goods_movement(self):
        """Tự động đẩy hàng lỗi sang vị trí kho Scrap để tách biệt tồn kho khả dụng"""
        for picking in self:
            damaged_moves = picking.move_ids.filtered(lambda m: m.wm_damaged_qty > 0)
            if not damaged_moves:
                continue

            scrap_location = self.env['stock.location'].search([
                ('usage', '=', 'inventory'),
                ('scrap_location', '=', True),
                ('company_id', '=', picking.company_id.id)
            ], limit=1)
            
            if not scrap_location:
                scrap_location = self.env.ref('stock.stock_location_scrapped', raise_if_not_found=False)

            if not scrap_location:
                continue

            for move in damaged_moves:
                self.env['stock.scrap'].sudo().create({
                    'product_id': move.product_id.id,
                    'scrap_qty': move.wm_damaged_qty,
                    'picking_id': picking.id,
                    'location_id': picking.location_id.id,
                    'scrap_location_id': scrap_location.id,
                    'company_id': picking.company_id.id,
                }).action_validate()
                
                picking.message_post(
                    body=_("Đã tự động cách ly %s %s hàng lỗi vào kho Scrap.") % (move.wm_damaged_qty, move.product_id.name)
                )

        self._sync_related_mer_request_state()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.id if len(self) == 1 else False,
            "view_mode": "form" if len(self) == 1 else "list,form",
            "views": [(False, "form")] if len(self) == 1 else [(False, "list"), (False, "form")],
            "target": "current",
        }

    def action_view_store_discrepancy_reports(self):
        self.ensure_one()
        reports = self.env["mer.discrepancy.report"].search([("picking_id", "=", self.id)])
        excess_reports = self.env["mer.excess.receipt"].search([("picking_id", "=", self.id)])
        if excess_reports and not reports:
            action = self.env["ir.actions.actions"]._for_xml_id("store_management.action_mer_excess_receipt")
            action["domain"] = [("id", "in", excess_reports.ids)]
            if len(excess_reports) == 1:
                action.update(
                    {
                        "res_id": excess_reports.id,
                        "view_mode": "form",
                        "views": [(False, "form")],
                    }
                )
            return action
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

    def _create_store_supplier_full_return_picking(self):
        self.ensure_one()
        return_picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id", "=", self.picking_type_id.warehouse_id.id),
            ],
            limit=1,
        )
        supplier_location = self.env.ref("stock.stock_location_suppliers", raise_if_not_found=False)
        if not return_picking_type or not supplier_location:
            raise UserError(_("Chưa cấu hình loại phiếu xuất hoặc địa điểm Nhà cung cấp để tạo phiếu trả hàng."))

        return_moves = []
        for move in self.move_ids.filtered(lambda current_move: current_move.state != "cancel" and current_move.product_uom_qty > 0):
            return_moves.append(
                (
                    0,
                    0,
                    {
                        "product_id": move.product_id.id,
                        "product_uom_qty": move.product_uom_qty,
                        "product_uom": move.product_uom.id,
                        "location_id": self.location_dest_id.id,
                        "location_dest_id": supplier_location.id,
                        "description_picking": _("[TRẢ NCC - TỪ CHỐI LÔ] %s từ phiếu %s")
                        % (move.product_id.display_name, self.name),
                    },
                )
            )
        if not return_moves:
            raise UserError(_("Phiếu không có dòng hàng hợp lệ để tạo phiếu trả NCC."))

        return_picking = self.env["stock.picking"].sudo().create(
            {
                "partner_id": self.partner_id.id,
                "picking_type_id": return_picking_type.id,
                "location_id": self.location_dest_id.id,
                "location_dest_id": supplier_location.id,
                "origin": _("Trả NCC do lô hàng lỗi: %s") % self.name,
                "move_ids": return_moves,
            }
        )
        return_picking.action_confirm()
        return return_picking

    def _create_store_central_damaged_return_picking(self):
        self.ensure_one()
        central_picking = self._get_store_receipt_central_source_picking()
        if not central_picking:
            raise UserError(_("Không xác định được phiếu Kho tổng -> Cửa hàng gốc để trả hàng lỗi."))

        damaged_location = self._get_or_create_central_damaged_location()
        picking_type = (
            central_picking.location_id.warehouse_id.int_type_id
            or central_picking.picking_type_id
        )
        if not picking_type:
            raise UserError(_("Chưa cấu hình loại phiếu nội bộ cho Kho tổng để nhận hàng lỗi."))

        return_moves = []
        for move in self.move_ids.filtered(lambda current_move: current_move.state != "cancel" and current_move.product_uom_qty > 0):
            return_qty = move.wm_damaged_qty if move.wm_damaged_qty > 0 else move.product_uom_qty
            return_moves.append(
                (
                    0,
                    0,
                    {
                        "product_id": move.product_id.id,
                        "product_uom_qty": return_qty,
                        "product_uom": move.product_uom.id,
                        "location_id": self.location_id.id,
                        "location_dest_id": damaged_location.id,
                        "description_picking": _("[HÀNG LỖI - TRẢ KHO TỔNG] %s từ phiếu %s")
                        % (move.product_id.display_name, self.name),
                    },
                )
            )
        if not return_moves:
            raise UserError(_("Phiếu không có dòng hàng hợp lệ để tạo phiếu trả hàng lỗi về Kho tổng."))

        return_picking = self.env["stock.picking"].sudo().create(
            {
                "partner_id": central_picking.partner_id.id,
                "picking_type_id": picking_type.id,
                "location_id": self.location_id.id,
                "location_dest_id": damaged_location.id,
                "origin": _("Trả hàng lỗi về Kho tổng: %s") % self.name,
                "mer_request_id": self.mer_request_id.id,
                "move_ids": return_moves,
            }
        )
        return_picking.action_confirm()
        return return_picking

    def _ensure_store_receipt_discrepancy_reports(
        self,
        submit_shortage=False,
        shortage_note=False,
        create_excess_report=True,
    ):
        self.ensure_one()
        destination_warehouse = self.location_dest_id.warehouse_id or self.picking_type_id.warehouse_id
        has_shortage = False
        has_overage = False
        for move in self.move_ids.filtered(lambda current_move: current_move.state != "cancel"):
            comparison = float_compare(
                move.quantity,
                move.product_uom_qty,
                precision_rounding=move.product_uom.rounding or 0.01,
            )
            if comparison < 0:
                has_shortage = True
                report = self.env["mer.discrepancy.report"].search(
                    [
                        ("picking_id", "=", self.id),
                        ("product_id", "=", move.product_id.id),
                        ("reason", "=", "shortage"),
                    ],
                    limit=1,
                )
                vals = {
                    "picking_id": self.id,
                    "purchase_id": self.purchase_id.id,
                    "warehouse_id": destination_warehouse.id if destination_warehouse else False,
                    "product_id": move.product_id.id,
                    "expected_qty": move.product_uom_qty,
                    "actual_qty": move.quantity,
                    "reason": "shortage",
                    "solution_notes": shortage_note or _("Được tạo/cập nhật khi Cửa hàng xác nhận nhập kho."),
                }
                if submit_shortage:
                    vals["submitted_to_merchandise"] = True
                if self._is_store_receipt_from_central():
                    vals["submitted_to_merchandise"] = True
                if report:
                    report.write(vals)
                else:
                    self.env["mer.discrepancy.report"].create(vals)
            elif comparison > 0:
                has_overage = True
                allow_excess_receipt = create_excess_report and self.store_route_type not in ("supplier_to_central", "supplier_to_store")
                if allow_excess_receipt:
                    report = self.env["mer.excess.receipt"].search(
                        [
                            ("picking_id", "=", self.id),
                            ("product_id", "=", move.product_id.id),
                            ("state", "!=", "done"),
                        ],
                        limit=1,
                    )
                    vals = {
                        "picking_id": self.id,
                        "product_id": move.product_id.id,
                        "expected_qty": move.product_uom_qty,
                        "actual_qty": move.quantity,
                        "notes": _("Được tạo/cập nhật khi Cửa hàng xác nhận nhập kho. Hệ thống chỉ nhập đúng số lượng theo PR/PO."),
                    }
                    if report:
                        report.write(vals)
                    else:
                        report = self.env["mer.excess.receipt"].create(vals)
                    if self._is_store_receipt_from_central() and report.state == "draft":
                        report.sudo().action_submit()
                else:
                    self.message_post(
                        body=_("<b>Từ chối dư hàng (Sản phẩm %s):</b> Phát hiện dư %s cái so với chứng từ. Do luồng nhận từ NCC, hệ thống tự động hoàn trả xe và chỉ nhập kho số lượng đúng PO.") % (
                            move.product_id.display_name,
                            move.quantity - move.product_uom_qty
                        ),
                        subtype_xmlid="mail.mt_note",
                    )
                move.quantity = move.product_uom_qty
        if has_shortage and has_overage:
            return "mixed"
        if has_shortage:
            return "shortage"
        if has_overage:
            return "overage"
        return "none"
    
    def _adjust_po_quantities_to_actual(self):
        """
        Bóp (Adjust) số lượng trên PO khớp với thực nhận khi có thiếu hàng.
        Điều này giúp giải phóng ngân sách ảo để Merchandise tạo PR/PO bù hàng mới.
        """
        from odoo.tools.float_utils import float_compare
        for picking in self:
            if not picking.purchase_id:
                continue
            
            # Điều chỉnh nếu phiếu này được xác nhận là có thiếu hàng (shortage) hoặc hàng lỗi bị từ chối (damaged_rejected)
            if picking.store_receipt_issue_type not in ('shortage', 'mixed', 'damaged_rejected'):
                continue

            for move in picking.move_ids.filtered(lambda m: m.state != 'cancel' and m.purchase_line_id):
                po_line = move.purchase_line_id
                
                # So sánh số lượng thực nhận (quantity) với số lượng trên PO (product_qty)
                comparison = float_compare(
                    move.quantity,
                    po_line.product_qty,
                    precision_rounding=move.product_uom.rounding or 0.01,
                )
                
                if comparison < 0:
                    old_qty = po_line.product_qty
                    try:
                        # Dùng sudo vì nhân viên kho thường không có quyền sửa PO
                        po_line.sudo().write({'product_qty': move.quantity})
                        picking.message_post(
                            body=_("<b>Điều chỉnh Ngân sách:</b> Đã tự động giảm số lượng PO line (%s) từ %s xuống %s để khớp với thực nhận, giúp giải phóng ngân sách cho đơn bù hàng.") % (
                                move.product_id.display_name,
                                old_qty,
                                move.quantity
                            )
                        )
                    except Exception as e:
                        _logger.warning("Không thể tự động điều chỉnh PO line cho sản phẩm %s: %s", move.product_id.display_name, str(e))

    def _notify_merchandise_store_receipt_rejected(self):
        merch_users = self._get_merchandise_notification_users()
        merch_partners = merch_users.mapped("partner_id").ids
        damage_details = self._build_damage_details_html() or _("<li>Lô hàng bị từ chối do có hàng hư hỏng.</li>")
        source_label = self.store_route_label or _("Nguồn giao")
        source_party = self.store_source_party_display or self.partner_id.display_name or _("Nguồn giao")
        body = _(
            "<b>Cửa hàng từ chối lô nhập do hàng lỗi.</b><br/>"
            "Phiếu <b>%s</b> thuộc luồng <b>%s</b>, nguồn giao <b>%s</b> đã bị đánh dấu Hàng lỗi và không nhập vào tồn kho.<br/>"
            "<b>Chi tiết lỗi:</b><ul>%s</ul>"
            "Merchandise cần theo dõi để bù hàng hoặc phối hợp Kho tổng xử lý hàng lỗi."
        ) % (
            self.name,
            source_label,
            source_party,
            damage_details,
        )
        if self.mer_request_id:
            if merch_partners:
                self.mer_request_id.message_subscribe(partner_ids=merch_partners)
            self.mer_request_id.message_post(
                body=body,
                partner_ids=merch_partners,
                subtype_xmlid="mail.mt_comment",
                subject=_("Cửa hàng từ chối lô nhập do hàng lỗi: %s") % self.name,
            )
        self.message_post(body=body, subtype_xmlid="mail.mt_note")

    def _create_store_receipt_damaged_reports(self):
        self.ensure_one()
        destination_warehouse = self.location_dest_id.warehouse_id or self.picking_type_id.warehouse_id
        reporting_party = _("Kho tổng") if self._is_central_supplier_receipt() else _("Cửa hàng")
        for move in self.move_ids.filtered(lambda current_move: current_move.state != "cancel" and current_move.wm_damaged_qty > 0):
            report = self.env["mer.discrepancy.report"].search(
                [
                    ("picking_id", "=", self.id),
                    ("product_id", "=", move.product_id.id),
                    ("reason", "=", "damaged"),
                ],
                limit=1,
            )
            vals = {
                "picking_id": self.id,
                "purchase_id": self.purchase_id.id,
                "warehouse_id": destination_warehouse.id if destination_warehouse else False,
                "product_id": move.product_id.id,
                "expected_qty": move.product_uom_qty,
                "actual_qty": 0.0,
                "damaged_qty": move.wm_damaged_qty,
                "reason": "damaged",
                "submitted_to_merchandise": True,
                "solution_notes": _(
                    "%(party)s từ chối toàn bộ lô nhập do phát hiện %(qty)s hàng hư hỏng. Ghi chú: %(note)s"
                )
                % {
                    "party": reporting_party,
                    "qty": move.wm_damaged_qty,
                    "note": move.wm_damage_note or "",
                },
            }
            if report:
                report.write(vals)
            else:
                self.env["mer.discrepancy.report"].create(vals)

    def _return_store_damaged_receipt_to_supplier(self):
        self.ensure_one()
        if self.store_route_type not in ("supplier_to_store", "central_to_store") or not self._is_store_receipt_for_qc():
            raise UserError(_("Chỉ áp dụng cho phiếu nhập về Cửa hàng."))
        if self.state in ("done", "cancel"):
            raise UserError(_("Phiếu này đã hoàn tất hoặc đã hủy, không thể xử lý hàng lỗi."))
        if not self.store_actual_check_done:
            raise UserError(_("Cần hoàn tất bước Kiểm hàng thực tế trước khi xử lý hàng lỗi."))

        active_moves = self.move_ids.filtered(lambda current_move: current_move.state != "cancel")
        damaged_moves = active_moves.filtered(lambda move: move.wm_damaged_qty > 0)
        if not damaged_moves:
            raise UserError(_("Chưa ghi nhận số lượng hư hỏng. Nếu hàng đạt, hãy dùng nút Xác nhận nhập hàng vào kho."))

        missing_note_moves = damaged_moves.filtered(lambda move: not move.wm_damage_note)
        if missing_note_moves:
            raise UserError(
                _("Vui lòng nhập Ghi chú lỗi cho các sản phẩm hư hỏng: %s")
                % ", ".join(missing_note_moves.mapped("product_id.display_name"))
            )

        self._create_store_receipt_damaged_reports()
        if self._is_store_receipt_from_central():
            return_picking = self._create_store_central_damaged_return_picking()
            message = _(
                "Đã tạo phiếu trả hàng lỗi về Kho tổng <b>%s</b>. Phiếu nhập Cửa hàng bị hủy, hàng lỗi không cộng vào tồn khả dụng của Cửa hàng hoặc Kho tổng."
            ) % return_picking.name
        else:
            return_picking = self._create_store_supplier_full_return_picking()
            message = _(
                "Đã tạo phiếu trả NCC <b>%s</b> cho toàn bộ lô hàng lỗi. Phiếu nhập gốc bị hủy, không cộng bất kỳ số lượng nào vào tồn kho của Cửa hàng."
            ) % return_picking.name
        self.env["mer.discrepancy.report"].search(
            [
                ("picking_id", "=", self.id),
                ("reason", "=", "damaged"),
            ]
        ).write({"return_picking_id": return_picking.id})
        self.write(
            {
                "store_receipt_issue_type": "damaged_rejected",
                "store_rejected_return_picking_id": return_picking.id,
                "wm_qc_status": "rejected",
                "wm_qc_checked_by": self.env.user.id,
                "wm_qc_checked_on": fields.Datetime.now(),
                "wm_qc_note": self.wm_qc_note or _("Từ chối toàn bộ lô giao do phát hiện hàng hư hỏng tại Cửa hàng."),
            }
        )
        # Tự động bóp PO để hoàn lại ngân sách cho đơn bù hàng
        self._adjust_po_quantities_to_actual()
        self.env["mer.purchase.request.line"].search(
            [("store_receipt_picking_id", "=", self.id)]
        ).with_context(store_skip_sync_rule=True).write({"internal_flow_state": "rejected"})
        
        # Hủy các báo cáo Thiếu/Dư đã tạo trước đó vì toàn bộ lô đã bị từ chối
        self.env["mer.discrepancy.report"].search([
            ("picking_id", "=", self.id),
            ("reason", "in", ["shortage", "overage"]),
            ("state", "!=", "cancel")
        ]).write({
            "state": "cancel", 
            "solution_notes": _("Báo cáo bị hủy do toàn bộ lô hàng đã bị từ chối vì có hàng hư hỏng.")
        })
        self.env["mer.excess.receipt"].search([
            ("picking_id", "=", self.id),
            ("state", "!=", "cancel")
        ]).write({
            "state": "cancel", 
            "notes": _("Phiếu bị hủy do toàn bộ lô hàng đã bị từ chối vì có hàng hư hỏng.")
        })

        self._notify_merchandise_store_receipt_rejected()
        self.message_post(body=message, subtype_xmlid="mail.mt_note")
        self.action_cancel()
        return return_picking

    def action_return_central_damaged_receipt_to_supplier(self):
        for picking in self:
            if not picking._is_central_supplier_receipt():
                raise UserError(_("Chỉ áp dụng cho phiếu NCC -> Kho tổng."))
            if picking.state in ("done", "cancel"):
                raise UserError(_("Phiếu này đã hoàn tất hoặc đã hủy, không thể trả hàng NCC."))
            if not picking.store_actual_check_done:
                raise UserError(_("Cần hoàn tất bước Kiểm hàng thực tế trước khi trả hàng NCC."))

            active_moves = picking.move_ids.filtered(lambda current_move: current_move.state != "cancel")
            damaged_moves = active_moves.filtered(lambda move: move.wm_damaged_qty > 0)
            if not damaged_moves:
                raise UserError(_("Chưa ghi nhận số lượng hư hỏng. Nếu hàng đạt, hãy dùng nút Xác nhận nhập hàng vào kho."))

            missing_note_moves = damaged_moves.filtered(lambda move: not move.wm_damage_note)
            if missing_note_moves:
                raise UserError(
                    _("Vui lòng nhập Ghi chú lỗi cho các sản phẩm hư hỏng: %s")
                    % ", ".join(missing_note_moves.mapped("product_id.display_name"))
                )

            picking._create_store_receipt_damaged_reports()
            return_picking = picking._create_store_supplier_full_return_picking()
            picking.write(
                {
                    "store_receipt_issue_type": "damaged_rejected",
                    "store_rejected_return_picking_id": return_picking.id,
                    "wm_qc_status": "rejected",
                    "wm_qc_checked_by": self.env.user.id,
                    "wm_qc_checked_on": fields.Datetime.now(),
                    "wm_qc_note": picking.wm_qc_note or _("Từ chối toàn bộ lô giao do phát hiện hàng hư hỏng tại Kho tổng."),
                }
            )
            # Tự động bóp PO để hoàn lại ngân sách cho đơn bù hàng
            picking._adjust_po_quantities_to_actual()
            
            # Hủy các báo cáo Thiếu/Dư đã tạo trước đó vì toàn bộ lô đã bị từ chối
            self.env["mer.discrepancy.report"].search([
                ("picking_id", "=", picking.id),
                ("reason", "in", ["shortage", "overage"]),
                ("state", "!=", "cancel")
            ]).write({
                "state": "cancel", 
                "solution_notes": _("Báo cáo bị hủy do toàn bộ lô hàng đã bị từ chối vì có hàng hư hỏng.")
            })
            self.env["mer.excess.receipt"].search([
                ("picking_id", "=", picking.id),
                ("state", "!=", "cancel")
            ]).write({
                "state": "cancel", 
                "notes": _("Phiếu bị hủy do toàn bộ lô hàng đã bị từ chối vì có hàng hư hỏng.")
            })
            picking.message_post(
                body=_(
                    "Đã tạo phiếu trả NCC <b>%s</b> cho toàn bộ lô hàng lỗi. Phiếu nhập gốc bị hủy, không cộng bất kỳ số lượng nào vào tồn kho Kho tổng."
                )
                % return_picking.name,
                subtype_xmlid="mail.mt_note",
            )
            picking.action_cancel()

        self._handle_central_supplier_qc_rejection()
        self._sync_related_mer_request_state()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.id if len(self) == 1 else False,
            "view_mode": "form" if len(self) == 1 else "list,form",
            "views": [(False, "form")] if len(self) == 1 else [(False, "list"), (False, "form")],
            "target": "current",
        }

    def action_return_store_damaged_receipt_to_supplier(self):
        for picking in self:
            picking._return_store_damaged_receipt_to_supplier()
        self._sync_related_mer_request_state()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.id if len(self) == 1 else False,
            "view_mode": "form" if len(self) == 1 else "list,form",
            "views": [(False, "form")] if len(self) == 1 else [(False, "list"), (False, "form")],
            "target": "current",
        }

    def action_confirm_store_receipt_to_stock(self):
        for picking in self:
            if picking.store_route_type not in ("supplier_to_store", "central_to_store") or not picking._is_store_receipt_for_qc():
                raise UserError(_("Chỉ áp dụng cho phiếu nhập về Cửa hàng."))
            if picking.state in ("done", "cancel"):
                continue
            if not picking.store_actual_check_done:
                raise UserError(_("Cần hoàn tất bước Kiểm hàng thực tế trước khi xác nhận nhập kho."))

            active_moves = picking.move_ids.filtered(lambda current_move: current_move.state != "cancel")
            if not active_moves:
                raise UserError(_("Phiếu không có dòng hàng hợp lệ để xác nhận."))

            damaged_moves = active_moves.filtered(lambda move: move.wm_damaged_qty > 0)
            if damaged_moves:
                raise UserError(_("Phiếu có hàng hư hỏng. Vui lòng dùng nút Xử lý hàng lỗi để từ chối lô hàng lỗi."))
                continue

            issue_type = picking._ensure_store_receipt_discrepancy_reports(
                submit_shortage=True,
                shortage_note=_("Cửa hàng nhận thiếu hàng. Báo cáo đã được gửi Merchandise để tạo PR bù hàng."),
            )
            picking.store_receipt_issue_type = issue_type

            # Tự động bóp PO nếu có thiếu hàng để giải phóng ngân sách
            if issue_type in ("shortage", "mixed"):
                picking._adjust_po_quantities_to_actual()

            if picking.wm_received_qty <= 0:
                picking.write(
                    {
                        "wm_qc_status": "passed",
                        "wm_qc_checked_by": self.env.user.id,
                        "wm_qc_checked_on": fields.Datetime.now(),
                    }
                )
                picking.action_cancel()
                picking.message_post(
                    body=_("Đã xác nhận không có số lượng thực nhận để nhập kho. Hệ thống đã tạo báo cáo thiếu hàng nếu có chênh lệch."),
                    subtype_xmlid="mail.mt_note",
                )
                continue

            if picking.wm_qc_status == "draft":
                picking.wm_qc_status = "checking"
            picking.with_context(
                skip_immediate=True,
                skip_backorder=True,
                cancel_backorder=True,
                picking_ids_not_to_backorder=picking.ids,
            ).action_qc_pass()

            if issue_type == "overage":
                picking.message_post(
                    body=_("Cửa hàng chỉ nhập đúng số lượng theo PR/PO. Phần dư đã được ghi nhận thành báo cáo nhận dư để gửi Merchandise."),
                    subtype_xmlid="mail.mt_note",
                )
            elif issue_type == "shortage":
                picking.message_post(
                    body=_("Cửa hàng đã nhập số lượng thực nhận và tạo báo cáo nhận thiếu hàng để gửi Merchandise."),
                    subtype_xmlid="mail.mt_note",
                )
            elif issue_type == "mixed":
                picking.message_post(
                    body=_("Cửa hàng đã nhập số lượng hợp lệ, đồng thời tạo báo cáo nhận thiếu và nhận dư hàng để Merchandise xử lý."),
                    subtype_xmlid="mail.mt_note",
                )

        self._sync_related_mer_request_state()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.id if len(self) == 1 else False,
            "view_mode": "form" if len(self) == 1 else "list,form",
            "views": [(False, "form")] if len(self) == 1 else [(False, "list"), (False, "form")],
            "target": "current",
        }

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
            validate_result = pickings_to_validate.with_context(
                skip_backorder=True,
                cancel_backorder=True,
                picking_ids_not_to_backorder=pickings_to_validate.ids,
            ).button_validate()

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
                _("Phải kiểm hàng thực tế đủ số lượng trước khi bắt đầu QC.")
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
