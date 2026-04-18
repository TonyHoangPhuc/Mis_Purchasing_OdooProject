from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MerPurchaseRequest(models.Model):
    _inherit = "mer.purchase.request"

    _store_blocking_states = ("draft", "submitted", "to_approve", "approved", "po_created")

    store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng yêu cầu",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Kho tổng / Nhà cung cấp",
        required=False,
    )
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("submitted", "Đã gửi (Chờ xử lý)"),
            ("to_approve", "Chờ Quản lý duyệt"),
            ("approved", "Được phê duyệt"),
            ("po_created", "Đang thực hiện"),
            ("done", "Hoàn tất"),
            ("rejected", "Từ chối"),
            ("cancel", "Hủy"),
        ],
        string="Trạng thái",
        default="draft",
        tracking=True,
    )
    internal_picking_count = fields.Integer(
        string="Phiếu điều chuyển",
        compute="_compute_document_counts",
    )
    purchase_order_count = fields.Integer(
        string="PO",
        compute="_compute_document_counts",
        search="_search_purchase_order_count",
    )
    can_create_processing = fields.Boolean(
        string="Can Create Processing",
        compute="_compute_document_counts",
    )
    internal_line_count = fields.Integer(
        string="Dòng nội bộ",
        compute="_compute_internal_flow_metrics",
        store=True,
    )
    pending_central_check_count = fields.Integer(
        string="Chờ Kho tổng kiểm",
        compute="_compute_internal_flow_metrics",
        store=True,
    )
    ready_delivery_count = fields.Integer(
        string="\u0110\u1ee7 h\u00e0ng ch\u1edd giao",
        compute="_compute_internal_flow_metrics",
        store=True,
    )
    waiting_delivery_count = fields.Integer(
        string="Chờ Supply Chain giao",
        compute="_compute_internal_flow_metrics",
        store=True,
    )
    insufficient_stock_count = fields.Integer(
        string="Chưa đủ hàng",
        compute="_compute_internal_flow_metrics",
        store=True,
    )
    central_flow_status = fields.Char(
        string="Trạng thái Kho tổng",
        compute="_compute_internal_flow_metrics",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        related="warehouse_id.company_id",
        readonly=True,
    )

    @api.onchange("store_id")
    def _onchange_store_id(self):
        if self.store_id:
            self.warehouse_id = self.store_id.warehouse_id

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id_sync_store(self):
        if self.warehouse_id and self.warehouse_id.mis_role == "store":
            store = self.env["store.store"].search([("warehouse_id", "=", self.warehouse_id.id)], limit=1)
            if store:
                self.store_id = store

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("store_id") and not vals.get("warehouse_id"):
                store = self.env["store.store"].browse(vals["store_id"])
                vals["warehouse_id"] = store.warehouse_id.id
            product_ids = self._extract_product_ids_from_line_commands(vals.get("line_ids", []))
            if vals.get("store_id") and product_ids:
                duplicate_request = self._find_duplicate_store_request(vals["store_id"], product_ids)
                if duplicate_request:
                    raise UserError(
                        _(
                            "Cửa hàng này đã có PR %(pr)s đang xử lý cho một hoặc nhiều sản phẩm đã chọn. "
                            "Vui lòng theo dõi hoặc hoàn tất PR hiện tại trước khi tạo thêm."
                        )
                        % {"pr": duplicate_request.name}
                    )
        return super().create(vals_list)

    @api.model
    def _extract_product_ids_from_line_commands(self, commands):
        product_ids = set()
        for command in commands or []:
            if not isinstance(command, (list, tuple)) or len(command) < 3:
                continue
            if command[0] == 0 and isinstance(command[2], dict) and command[2].get("product_id"):
                product_ids.add(command[2]["product_id"])
        return list(product_ids)

    @api.model
    def _find_duplicate_store_request(self, store_id, product_ids, exclude_request_id=None):
        if not store_id or not product_ids:
            return self.browse()

        domain = [
            ("store_id", "=", store_id),
            ("state", "in", list(self._store_blocking_states)),
            ("line_ids.product_id", "in", product_ids),
        ]
        if exclude_request_id:
            domain.append(("id", "!=", exclude_request_id))
        return self.search(domain, limit=1)

    def _check_store_menu_action_allowed(self, allowed_methods=None):
        allowed_methods = allowed_methods or set()
        if self.env.context.get("from_store_menu") and self.env.user.has_group("store_management.group_store_user"):
            current_method = self.env.context.get("store_current_action")
            if current_method not in allowed_methods:
                raise UserError(
                    _("Từ menu Cửa hàng, bạn chỉ được tạo PR, gửi PR và theo dõi trạng thái xử lý.")
                )

    @api.depends("line_ids.fulfillment_method", "line_ids.purchase_order_id", "line_ids.internal_picking_id")
    def _compute_document_counts(self):
        for request in self:
            request.purchase_order_count = len(request.line_ids.mapped("purchase_order_id"))
            request.internal_picking_count = len(request.line_ids.mapped("internal_picking_id"))
            request.can_create_processing = bool(
                request.line_ids.filtered(
                    lambda line: line.fulfillment_method
                    and not line.purchase_order_id
                    and not line.internal_picking_id
                )
            )

    @api.depends(
        "line_ids.fulfillment_method",
        "line_ids.internal_flow_state",
        "line_ids.purchase_order_id",
        "line_ids.purchase_order_id.picking_ids.state",
        "line_ids.purchase_order_id.picking_ids.wm_qc_status",
        "line_ids.purchase_order_id.picking_ids.picking_type_id.warehouse_id",
        "line_ids.internal_picking_id.state",
        "line_ids.internal_picking_id.wm_qc_status",
    )
    def _compute_internal_flow_metrics(self):
        for request in self:
            internal_lines = request.line_ids.filtered(
                lambda line: line.fulfillment_method in ("internal", "supplier_central")
            )
            central_lines = request.line_ids.filtered(
                lambda line: line.fulfillment_method in ("internal", "supplier_central")
            )
            request.internal_line_count = len(central_lines)
            request.pending_central_check_count = len(
                internal_lines.filtered(lambda line: line.internal_flow_state == "pending_check")
            )
            request.ready_delivery_count = len(
                internal_lines.filtered(lambda line: line.internal_flow_state == "ready_delivery")
            )
            request.insufficient_stock_count = len(
                internal_lines.filtered(lambda line: line.internal_flow_state == "waiting_stock")
            )
            waiting_receipt_count = len(
                central_lines.filtered(
                    lambda line: line.fulfillment_method == "supplier_central"
                    and line.purchase_order_id
                    and not line.purchase_order_id.picking_ids.filtered(
                        lambda picking: picking.picking_type_code == "incoming"
                        and picking.picking_type_id.warehouse_id
                        and getattr(picking.picking_type_id.warehouse_id, "mis_role", False) == "central"
                        and (picking.state == "done" or picking.wm_qc_status == "rejected")
                    )
                )
            )
            request.waiting_delivery_count = len(
                central_lines.filtered(
                    lambda line: line.internal_flow_state == "waiting_delivery"
                    and line.internal_picking_id.state not in ("done", "cancel")
                )
            )
            waiting_store_receipt_count = len(
                central_lines.filtered(
                    lambda line: line.internal_flow_state == "waiting_store_receipt"
                    and line.store_receipt_picking_id
                    and line.store_receipt_picking_id.state not in ("done", "cancel")
                )
            )
            has_rejected_line = any(
                line.internal_flow_state == "rejected"
                or (line.internal_picking_id and line.internal_picking_id.wm_qc_status == "rejected")
                or (
                    line.fulfillment_method == "supplier_central"
                    and line.purchase_order_id.picking_ids.filtered(
                        lambda picking: picking.picking_type_code == "incoming"
                        and picking.picking_type_id.warehouse_id
                        and getattr(picking.picking_type_id.warehouse_id, "mis_role", False) == "central"
                        and picking.wm_qc_status == "rejected"
                    )
                )
                for line in central_lines
            )

            if not central_lines:
                request.central_flow_status = _("Không qua Kho tổng")
            elif request.insufficient_stock_count:
                request.central_flow_status = _("Kho tổng chưa đủ hàng")
            elif request.pending_central_check_count:
                request.central_flow_status = _("Chờ Kho tổng kiểm hàng để giao")
            elif request.ready_delivery_count:
                request.central_flow_status = _("\u0110\u1ee7 h\u00e0ng, ch\u1edd x\u00e1c nh\u1eadn giao")
            elif waiting_receipt_count:
                request.central_flow_status = _("Chờ NCC giao Kho tổng")
            elif request.waiting_delivery_count:
                request.central_flow_status = _("Chờ Kho tổng giao hàng")
            elif has_rejected_line:
                request.central_flow_status = _("Có lô hàng lỗi")
            elif all(request._is_line_logistically_completed(line) for line in central_lines):
                request.central_flow_status = _("Đã giao hàng về cửa hàng")
            else:
                request.central_flow_status = _("Đang xử lý")

    @api.onchange("line_ids")
    def _onchange_line_ids(self):
        return

    def _get_relevant_supply_warehouses(self):
        self.ensure_one()
        warehouses = self.env["stock.warehouse"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("mis_role", "=", "central"),
            ]
        )
        if warehouses:
            return warehouses
        return self.env["stock.warehouse"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("id", "!=", self.warehouse_id.id),
                ("mis_role", "!=", "store"),
            ]
        )

    def _get_default_internal_source_warehouse(self):
        self.ensure_one()
        store = self.store_id
        if store:
            warehouse = store._get_central_warehouse()
            if warehouse and warehouse != self.warehouse_id:
                return warehouse
        return self.env["stock.warehouse"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("mis_role", "=", "central"),
            ],
            limit=1,
        )

    def _validate_merchandise_processing(self):
        for request in self:
            request._ensure_approved_quantities()
            if not request.line_ids:
                raise UserError(_("PR phải có ít nhất một sản phẩm trước khi trình quản lý."))
            for line in request.line_ids:
                if line.approved_qty <= 0:
                    raise UserError(
                        _(
                            "S\u1ea3n ph\u1ea9m %s ph\u1ea3i c\u00f3 s\u1ed1 l\u01b0\u1ee3ng "
                            "\u0111\u01b0\u1ee3c duy\u1ec7t l\u1edbn h\u01a1n 0."
                        )
                        % line.product_id.display_name
                    )
                if line.approved_qty > line.product_qty:
                    raise UserError(
                        _(
                            "S\u1ea3n ph\u1ea9m %s c\u00f3 s\u1ed1 l\u01b0\u1ee3ng \u0111\u01b0\u1ee3c "
                            "duy\u1ec7t kh\u00f4ng \u0111\u01b0\u1ee3c l\u1edbn h\u01a1n s\u1ed1 "
                            "l\u01b0\u1ee3ng y\u00eau c\u1ea7u."
                        )
                        % line.product_id.display_name
                    )
                if not line.fulfillment_method:
                    raise UserError(_("Vui lòng chọn phương án đáp ứng cho tất cả sản phẩm trước khi trình quản lý."))
                if line.fulfillment_method == "internal":
                    if not line.source_warehouse_id:
                        raise UserError(
                            _("Sản phẩm %s chưa chọn kho nguồn để điều chuyển nội bộ.")
                            % line.product_id.display_name
                        )
                elif line.fulfillment_method in ("supplier", "supplier_central") and not line.supplier_id:
                    raise UserError(_("Sản phẩm %s chưa có NCC đáp ứng.") % line.product_id.display_name)

    def _ensure_approved_quantities(self):
        for request in self:
            missing_approved_qty_lines = request.line_ids.filtered(lambda line: not line.approved_qty)
            for line in missing_approved_qty_lines:
                line.approved_qty = line.product_qty

    def _get_pending_internal_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.fulfillment_method in ("internal", "supplier_central")
            and line.internal_flow_state in ("pending_check", "waiting_stock")
            and not line.internal_picking_id
        )

    def _get_ready_internal_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.fulfillment_method in ("internal", "supplier_central")
            and line.internal_flow_state == "ready_delivery"
            and not line.internal_picking_id
        )

    def _build_central_stock_check_message(self, ready_lines, insufficient_lines):
        self.ensure_one()
        message_lines = [
            _("Kho tong da kiem tra ton kho cho PR <b>%s</b>.") % self.name,
        ]
        if ready_lines:
            message_lines.append(_("Cac dong du hang cho giao:"))
            message_lines.append(
                "<ul>%s</ul>"
                % "".join(
                    "<li>%s: kha dung %.2f, can giao %.2f, sau giao con %.2f.</li>"
                    % (
                        line.product_id.display_name,
                        line.source_available_qty,
                        line.approved_qty,
                        line.remaining_after_dispatch_qty,
                    )
                    for line in ready_lines
                )
            )
        if insufficient_lines:
            message_lines.append(_("Cac dong chua du hang:"))
            message_lines.append(
                "<ul>%s</ul>"
                % "".join(
                    "<li>%s: kha dung %.2f, can giao %.2f, thieu %.2f.</li>"
                    % (
                        line.product_id.display_name,
                        line.source_available_qty,
                        line.approved_qty,
                        abs(line.remaining_after_dispatch_qty),
                    )
                    for line in insufficient_lines
                )
            )
        return "".join(message_lines)

    def _is_line_logistically_completed(self, line):
        self.ensure_one()
        if line.fulfillment_method == "supplier":
            if not line.purchase_order_id:
                return False
            receipt_pickings = line.purchase_order_id.picking_ids.filtered(
                lambda picking: picking.picking_type_code == "incoming"
                and picking.picking_type_id.warehouse_id == line.request_warehouse_id
            )
            return bool(
                receipt_pickings.filtered(
                    lambda picking: picking.state == "done" or picking.wm_qc_status == "rejected"
                )
            )

        if line.fulfillment_method == "supplier_central":
            if not line.purchase_order_id:
                return False
            receipt_pickings = line.purchase_order_id.picking_ids.filtered(
                lambda picking: picking.picking_type_code == "incoming"
                and picking.picking_type_id.warehouse_id
                and getattr(picking.picking_type_id.warehouse_id, "mis_role", False) == "central"
            )
            if receipt_pickings.filtered(lambda picking: picking.wm_qc_status == "rejected"):
                return True
            if not receipt_pickings.filtered(lambda picking: picking.state == "done"):
                return False
            return line.internal_flow_state in ("delivered", "rejected")

        if line.fulfillment_method == "internal":
            return line.internal_flow_state in ("delivered", "rejected")

        return False

    def _sync_state_with_logistics(self):
        active_states = {"approved", "po_created", "done"}
        for request in self.filtered(lambda req: req.state in active_states):
            lines = request.line_ids.filtered(
                lambda line: line.fulfillment_method in ("supplier", "supplier_central", "internal")
            )
            if not lines:
                continue

            all_completed = all(request._is_line_logistically_completed(line) for line in lines)
            has_started_documents = any(line.purchase_order_id or line.internal_picking_id for line in lines)

            if all_completed:
                request.state = "done"
            elif has_started_documents:
                request.state = "po_created"

    def _create_internal_pickings_for_lines(self, lines):
        self.ensure_one()
        lines = lines.filtered(lambda line: not line.internal_picking_id)
        if not lines:
            return self.env["stock.picking"]

        grouped_lines = defaultdict(lambda: self.env["mer.purchase.request.line"])
        for line in lines:
            source_warehouse = line.source_warehouse_id or self._get_default_internal_source_warehouse()
            if not source_warehouse:
                raise UserError(
                    _("Không xác định được kho nguồn để chuyển hàng cho PR %s.") % self.display_name
                )
            grouped_lines[source_warehouse.id] |= line

        created_pickings = self.env["stock.picking"]
        transit_location = self.company_id.internal_transit_location_id or self.env.ref('stock.stock_location_inter_company', raise_if_not_found=False)

        for source_warehouse_id, grouped_request_lines in grouped_lines.items():
            source_warehouse = self.env["stock.warehouse"].browse(source_warehouse_id)
            dest_location = transit_location if transit_location else self.warehouse_id.lot_stock_id

            # 1. Create Central Delivery Picking (WH -> Transit)
            central_picking = self.env["stock.picking"].sudo().create(
                {
                    "partner_id": self.store_id.partner_id.id if self.store_id and self.store_id.partner_id else False,
                    "picking_type_id": source_warehouse.out_type_id.id or source_warehouse.int_type_id.id,
                    "location_id": source_warehouse.lot_stock_id.id,
                    "location_dest_id": dest_location.id,
                    "origin": self.name + _(" - Giao hàng"),
                    "scheduled_date": fields.Datetime.now(),
                    "move_ids": [
                        (
                            0,
                            0,
                            {
                                "description_picking": line.product_id.display_name,
                                "product_id": line.product_id.id,
                                "product_uom_qty": line.approved_qty,
                                "product_uom": line.product_uom_id.id,
                                "location_id": source_warehouse.lot_stock_id.id,
                                "location_dest_id": dest_location.id,
                            },
                        )
                        for line in grouped_request_lines
                    ],
                }
            )
            central_picking.action_confirm()
            central_picking.action_assign()
            
            store_picking = central_picking
            # 2. Create Store Receipt Picking (Transit -> Store) if transit exists
            if transit_location:
                store_picking = self.env["stock.picking"].sudo().create(
                    {
                        "partner_id": source_warehouse.partner_id.id if source_warehouse.partner_id else False,
                        "picking_type_id": self.warehouse_id.in_type_id.id,
                        "location_id": dest_location.id,
                        "location_dest_id": self.warehouse_id.lot_stock_id.id,
                        "origin": self.name + _(" - Nhận hàng"),
                        "scheduled_date": fields.Datetime.now(),
                        "move_ids": [
                            (
                                0,
                                0,
                                {
                                    "description_picking": line.product_id.display_name,
                                    "product_id": line.product_id.id,
                                    "product_uom_qty": line.approved_qty,
                                    "product_uom": line.product_uom_id.id,
                                    "location_id": dest_location.id,
                                    "location_dest_id": self.warehouse_id.lot_stock_id.id,
                                    "move_orig_ids": [(6, 0, [central_move.id])],
                                },
                            )
                            for line, central_move in zip(grouped_request_lines, central_picking.move_ids)
                        ],
                    }
                )
                store_picking.action_confirm()
            
            grouped_request_lines.with_context(store_skip_sync_rule=True).write(
                {
                    "internal_picking_id": central_picking.id,
                    "store_receipt_picking_id": store_picking.id if store_picking != central_picking else False,
                    "internal_flow_state": "waiting_delivery",
                }
            )
            created_pickings |= central_picking | store_picking

        if created_pickings:
            self.state = "po_created"
        return created_pickings

    def action_submit(self):
        self = self.with_context(store_current_action="action_submit")
        self._check_store_menu_action_allowed({"action_submit"})
        for request in self.filtered("store_id"):
            duplicate_request = self._find_duplicate_store_request(
                request.store_id.id,
                request.line_ids.mapped("product_id").ids,
                exclude_request_id=request.id,
            )
            if duplicate_request:
                    raise UserError(
                        _(
                            "Cửa hàng này đã có PR %(pr)s đang xử lý cho một hoặc nhiều sản phẩm trong phiếu hiện tại."
                        )
                        % {"pr": duplicate_request.name}
                    )
        return super().action_submit()

    def action_send_to_manager(self):
        self = self.with_context(store_current_action="action_send_to_manager")
        self._check_store_menu_action_allowed()
        self._validate_merchandise_processing()
        return super().action_send_to_manager()

    def action_approve(self):
        self = self.with_context(store_current_action="action_approve")
        self._check_store_menu_action_allowed()
        return super().action_approve()

    def action_reject(self):
        self = self.with_context(store_current_action="action_reject")
        self._check_store_menu_action_allowed()
        return super().action_reject()

    def action_draft(self):
        self = self.with_context(store_current_action="action_draft")
        self._check_store_menu_action_allowed()
        return super().action_draft()

    def action_cancel(self):
        self = self.with_context(store_current_action="action_cancel")
        self._check_store_menu_action_allowed()
        return super().action_cancel()

    def action_create_po(self):
        self = self.with_context(store_current_action="action_create_po")
        self._check_store_menu_action_allowed()
        self.ensure_one()
        self._ensure_approved_quantities()
        if self.state not in ("approved", "po_created"):
            raise UserError(_("PR cần ở trạng thái đã duyệt hoặc đang thực hiện trước khi khởi tạo xử lý."))

        lines_to_process = self.line_ids.filtered(
            lambda line: line.fulfillment_method and not line.purchase_order_id and not line.internal_picking_id
        )
        if not lines_to_process:
            raise UserError(_("Tất cả dòng sản phẩm của PR này đã được khởi tạo xử lý rồi."))

        created_orders = self.env["purchase.order"]
        supplier_groups = defaultdict(lambda: self.env["mer.purchase.request.line"])

        for line in lines_to_process:
            if line.fulfillment_method in ("supplier", "supplier_central"):
                supplier_groups[(line.supplier_id.id, line.fulfillment_method)] |= line

        for (supplier_id, fulfillment_method), grouped_lines in supplier_groups.items():
            supplier = self.env["res.partner"].browse(supplier_id)
            target_warehouse = (
                self._get_default_internal_source_warehouse()
                if fulfillment_method == "supplier_central"
                else self.warehouse_id
            )
            if not target_warehouse:
                raise UserError(_("Chưa cấu hình Kho tổng để tiếp nhận hàng từ NCC."))
            order = self.env["purchase.order"].sudo().create(
                {
                    "partner_id": supplier.id,
                    "origin": self.name,
                    "date_order": fields.Datetime.now(),
                    "picking_type_id": target_warehouse.in_type_id.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": line.product_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.approved_qty,
                                "product_uom_id": line.product_uom_id.id,
                                "price_unit": line.product_id.standard_price,
                                "date_planned": fields.Datetime.now(),
                            },
                        )
                        for line in grouped_lines
                    ],
                }
            )
            order.button_confirm()
            write_vals = {"purchase_order_id": order.id}
            if fulfillment_method == "supplier_central":
                write_vals["internal_flow_state"] = "waiting_receipt"
                for line in grouped_lines.filtered(lambda request_line: not request_line.source_warehouse_id):
                    line.source_warehouse_id = target_warehouse
            grouped_lines.with_context(store_skip_sync_rule=True).write(write_vals)
            created_orders |= order

        internal_lines = lines_to_process.filtered(lambda line: line.fulfillment_method == "internal")
        if internal_lines:
            internal_lines.with_context(store_skip_sync_rule=True).write({"internal_flow_state": "pending_check"})

        if created_orders or internal_lines:
            self.state = "po_created"

        return {
            "type": "ir.actions.act_window",
            "res_model": "mer.purchase.request",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_confirm_central_stock(self):
        self.ensure_one()
        self._ensure_approved_quantities()
        pending_lines = self._get_pending_internal_lines()
        if not pending_lines:
            raise UserError(_("PR này không có dòng nào đang chờ Kho tổng kiểm hàng để giao."))

        insufficient_lines = pending_lines.filtered(lambda line: line.source_available_qty < line.approved_qty)
        if insufficient_lines:
            insufficient_lines.with_context(store_skip_sync_rule=True).write({"internal_flow_state": "waiting_stock"})
            available_lines = pending_lines - insufficient_lines
            if available_lines:
                available_lines.with_context(store_skip_sync_rule=True).write({"internal_flow_state": "pending_check"})
            self.message_post(
                body=_(
                    "Kho tổng chưa đủ hàng để giao cho các sản phẩm: %s. Đơn được tạm giữ ở trạng thái Chưa đủ hàng."
                )
                % ", ".join(insufficient_lines.mapped("product_id.display_name"))
            )
            return {
                "type": "ir.actions.act_window",
                "res_model": "mer.purchase.request",
                "res_id": self.id,
                "view_mode": "form",
                "target": "current",
                "context": dict(self.env.context, central_check_menu=1),
            }

        self._create_internal_pickings_for_lines(pending_lines)
        self.message_post(body=_("Kho tổng đã kiểm đủ hàng và tạo phiếu giao cho cửa hàng."))

        return {
            "type": "ir.actions.act_window",
            "res_model": "mer.purchase.request",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": dict(self.env.context, central_check_menu=1),
        }

    ready_delivery_count = fields.Integer(
        string="\u0110\u1ee7 h\u00e0ng ch\u1edd giao",
        compute="_compute_internal_flow_metrics",
        store=True,
    )

    @api.depends(
        "line_ids.fulfillment_method",
        "line_ids.internal_flow_state",
        "line_ids.purchase_order_id",
        "line_ids.purchase_order_id.picking_ids.state",
        "line_ids.purchase_order_id.picking_ids.wm_qc_status",
        "line_ids.purchase_order_id.picking_ids.picking_type_id.warehouse_id",
        "line_ids.internal_picking_id.state",
        "line_ids.internal_picking_id.wm_qc_status",
        "line_ids.store_receipt_picking_id.state",
        "line_ids.store_receipt_picking_id.wm_qc_status",
    )
    def _compute_internal_flow_metrics(self):
        for request in self:
            internal_lines = request.line_ids.filtered(
                lambda line: line.fulfillment_method in ("internal", "supplier_central")
            )
            request.internal_line_count = len(internal_lines)
            request.pending_central_check_count = len(
                internal_lines.filtered(lambda line: line.internal_flow_state == "pending_check")
            )
            request.ready_delivery_count = len(
                internal_lines.filtered(lambda line: line.internal_flow_state == "ready_delivery")
            )
            request.insufficient_stock_count = len(
                internal_lines.filtered(lambda line: line.internal_flow_state == "waiting_stock")
            )
            waiting_receipt_count = len(
                internal_lines.filtered(
                    lambda line: line.fulfillment_method == "supplier_central"
                    and line.purchase_order_id
                    and not line.purchase_order_id.picking_ids.filtered(
                        lambda picking: picking.picking_type_code == "incoming"
                        and picking.picking_type_id.warehouse_id
                        and getattr(picking.picking_type_id.warehouse_id, "mis_role", False) == "central"
                        and (picking.state == "done" or picking.wm_qc_status == "rejected")
                    )
                )
            )
            request.waiting_delivery_count = len(
                internal_lines.filtered(
                    lambda line: line.internal_flow_state == "waiting_delivery"
                    and line.internal_picking_id.state not in ("done", "cancel")
                )
            )
            waiting_store_receipt_count = len(
                internal_lines.filtered(
                    lambda line: line.internal_flow_state == "waiting_store_receipt"
                    and line.store_receipt_picking_id
                    and line.store_receipt_picking_id.state not in ("done", "cancel")
                )
            )
            has_rejected_line = any(
                line.internal_flow_state == "rejected"
                or (line.internal_picking_id and line.internal_picking_id.wm_qc_status == "rejected")
                or (line.store_receipt_picking_id and line.store_receipt_picking_id.wm_qc_status == "rejected")
                or (
                    line.fulfillment_method == "supplier_central"
                    and line.purchase_order_id.picking_ids.filtered(
                        lambda picking: picking.picking_type_code == "incoming"
                        and picking.picking_type_id.warehouse_id
                        and getattr(picking.picking_type_id.warehouse_id, "mis_role", False) == "central"
                        and picking.wm_qc_status == "rejected"
                    )
                )
                for line in internal_lines
            )

            if not internal_lines:
                request.central_flow_status = _("Khong qua Kho tong")
            elif request.insufficient_stock_count:
                request.central_flow_status = _("Kho tong chua du hang")
            elif request.pending_central_check_count:
                request.central_flow_status = _("Cho Kho tong kiem hang de giao")
            elif request.ready_delivery_count:
                request.central_flow_status = _("\u0110\u1ee7 h\u00e0ng, ch\u1edd x\u00e1c nh\u1eadn giao")
            elif waiting_receipt_count:
                request.central_flow_status = _("Cho NCC giao Kho tong")
            elif request.waiting_delivery_count:
                request.central_flow_status = _("Cho Kho tong giao hang")
            elif waiting_store_receipt_count:
                request.central_flow_status = _("Cho cua hang nhan hang")
            elif has_rejected_line:
                request.central_flow_status = _("Co lo hang loi")
            elif all(request._is_line_logistically_completed(line) for line in internal_lines):
                request.central_flow_status = _("Da giao hang ve cua hang")
            else:
                request.central_flow_status = _("Dang xu ly")

    def _get_ready_internal_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.fulfillment_method in ("internal", "supplier_central")
            and line.internal_flow_state == "ready_delivery"
            and not line.internal_picking_id
        )

    def _build_central_stock_check_message(self, ready_lines, insufficient_lines):
        self.ensure_one()
        chunks = [_("Kho t\u1ed5ng \u0111\u00e3 ki\u1ec3m tra t\u1ed3n kho cho PR <b>%s</b>.") % self.name]
        if ready_lines:
            chunks.append(_("C\u00e1c d\u00f2ng \u0111\u1ee7 h\u00e0ng ch\u1edd giao:"))
            chunks.append(
                "<ul>%s</ul>"
                % "".join(
                    "<li>%s: kha dung %.2f, can giao %.2f, sau giao con %.2f.</li>"
                    % (
                        line.product_id.display_name,
                        line.source_available_qty,
                        line.approved_qty,
                        line.remaining_after_dispatch_qty,
                    )
                    for line in ready_lines
                )
            )
        if insufficient_lines:
            chunks.append(_("C\u00e1c d\u00f2ng ch\u01b0a \u0111\u1ee7 h\u00e0ng:"))
            chunks.append(
                "<ul>%s</ul>"
                % "".join(
                    "<li>%s: kha dung %.2f, can giao %.2f, thieu %.2f.</li>"
                    % (
                        line.product_id.display_name,
                        line.source_available_qty,
                        line.approved_qty,
                        abs(line.remaining_after_dispatch_qty),
                    )
                    for line in insufficient_lines
                )
            )
        return "".join(chunks)

    def action_confirm_central_stock(self):
        self.ensure_one()
        self._ensure_approved_quantities()
        pending_lines = self._get_pending_internal_lines()
        if not pending_lines:
            raise UserError(_("PR n\u00e0y kh\u00f4ng c\u00f3 d\u00f2ng n\u00e0o \u0111ang ch\u1edd Kho t\u1ed5ng ki\u1ec3m h\u00e0ng \u0111\u1ec3 giao."))

        ready_lines = pending_lines.filtered(lambda line: line.source_available_qty >= line.approved_qty)
        insufficient_lines = pending_lines - ready_lines
        if ready_lines:
            ready_lines.with_context(store_skip_sync_rule=True).write({"internal_flow_state": "ready_delivery"})
        if insufficient_lines:
            insufficient_lines.with_context(store_skip_sync_rule=True).write({"internal_flow_state": "waiting_stock"})

        self.message_post(body=self._build_central_stock_check_message(ready_lines, insufficient_lines))
        return {
            "type": "ir.actions.act_window",
            "res_model": "mer.purchase.request",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": dict(self.env.context, central_check_menu=1),
        }

    def action_confirm_central_stock_ready(self):
        self.ensure_one()
        ready_lines = self._get_ready_internal_lines()
        if not ready_lines:
            raise UserError(_("PR n\u00e0y ch\u01b0a c\u00f3 d\u00f2ng n\u00e0o \u0111\u1ee7 h\u00e0ng \u0111\u1ec3 x\u00e1c nh\u1eadn giao."))

        created_pickings = self._create_internal_pickings_for_lines(ready_lines)
        self.message_post(
            body=_("Kho t\u1ed5ng \u0111\u00e3 x\u00e1c nh\u1eadn \u0111\u1ee7 h\u00e0ng v\u00e0 chuy\u1ec3n %s d\u00f2ng sang danh s\u00e1ch \u0110\u01a1n c\u1ea7n giao.")
            % len(ready_lines)
        )
        central_pickings = created_pickings.filtered(lambda picking: picking._is_central_to_store_transfer())
        action = self.env["ir.actions.actions"]._for_xml_id("store_management.action_warehouse_pending_deliveries")
        action["domain"] = [("id", "in", central_pickings.ids)]
        return action


class MerPurchaseRequestLine(models.Model):
    _inherit = "mer.purchase.request.line"
    approved_qty = fields.Float(
        string="S\u1ed1 l\u01b0\u1ee3ng \u0111\u01b0\u1ee3c duy\u1ec7t",
        digits="Product Unit of Measure",
        default=0.0,
        tracking=True,
    )

    request_company_id = fields.Many2one(
        "res.company",
        string="Công ty yêu cầu",
        related="request_id.company_id",
        readonly=True,
    )
    request_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Kho đích",
        related="request_id.warehouse_id",
        readonly=True,
    )
    fulfillment_method = fields.Selection(
        [
            ("internal", "Kho tổng có sẵn"),
            ("supplier_central", "NCC giao về Kho tổng"),
            ("supplier", "NCC giao thẳng Cửa hàng"),
        ],
        string="Phương án đáp ứng",
        tracking=True,
    )
    source_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Kho nguồn",
        domain="[('company_id', '=', request_company_id), ('mis_role', '=', 'central')]",
    )
    supplier_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        domain="[('category_id.name', '=', 'NCC')]",
    )
    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="PO đã tạo",
        readonly=True,
        copy=False,
    )
    internal_picking_id = fields.Many2one(
        "stock.picking",
        string="Phiếu điều chuyển",
        readonly=True,
        copy=False,
    )
    internal_flow_state = fields.Selection(
        [
            ("not_applicable", "Không áp dụng"),
            ("pending_check", "Chờ Kho tổng kiểm"),
            ("waiting_receipt", "Chờ NCC giao Kho tổng"),
            ("waiting_stock", "Chưa đủ hàng"),
            ("waiting_delivery", "Chờ Kho tổng giao"),
            ("rejected", "Hàng lỗi"),
            ("delivered", "Đã giao cửa hàng"),
        ],
        string="Tiến trình hậu cần",
        default="not_applicable",
        copy=False,
        tracking=True,
    )
    route_status_display = fields.Char(
        string="Trạng thái xử lý",
        compute="_compute_route_status_display",
    )
    central_on_hand_qty = fields.Float(
        string="Tồn kho tổng",
        compute="_compute_supply_metrics",
        digits="Product Unit of Measure",
    )
    central_available_qty = fields.Float(
        string="Khả dụng kho tổng",
        compute="_compute_supply_metrics",
        digits="Product Unit of Measure",
    )
    other_warehouses_qty = fields.Float(
        string="Tồn các kho khác",
        compute="_compute_supply_metrics",
        digits="Product Unit of Measure",
    )
    source_available_qty = fields.Float(
        string="Khả dụng kho nguồn",
        compute="_compute_supply_metrics",
        digits="Product Unit of Measure",
    )
    availability_breakdown = fields.Text(
        string="Tồn theo kho",
        compute="_compute_supply_metrics",
    )

    def _get_product_supplier_candidates(self):
        self.ensure_one()
        supplier_category = self.env["res.partner.category"].search([("name", "=", "NCC")], limit=1)
        partners = self.product_id.seller_ids.mapped("partner_id")
        if supplier_category:
            return partners.filtered(lambda partner: supplier_category in partner.category_id)
        return self.env["res.partner"]

    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute(
            """
            UPDATE mer_purchase_request_line
               SET approved_qty = product_qty
             WHERE approved_qty IS NULL OR approved_qty = 0
            """
        )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "approved_qty" not in vals:
                vals["approved_qty"] = vals.get("product_qty", 1.0)
        return super().create(vals_list)

    def write(self, vals):
        if "product_qty" in vals and "approved_qty" not in vals:
            draft_lines = self.filtered(lambda line: line.request_id.state == "draft")
            non_draft_lines = self - draft_lines
            result = True
            if draft_lines:
                draft_vals = dict(vals, approved_qty=vals["product_qty"])
                result = super(MerPurchaseRequestLine, draft_lines).write(draft_vals) and result
            if non_draft_lines:
                result = super(MerPurchaseRequestLine, non_draft_lines).write(vals) and result
            return result
        return super().write(vals)

    @api.onchange("fulfillment_method", "product_id")
    def _onchange_fulfillment_method(self):
        if self.fulfillment_method == "internal":
            self.supplier_id = False
            self.source_warehouse_id = self.request_id._get_default_internal_source_warehouse()
            self.internal_flow_state = "not_applicable"
        elif self.fulfillment_method == "supplier_central":
            self.source_warehouse_id = self.request_id._get_default_internal_source_warehouse()
            self.internal_flow_state = "not_applicable"
            self.supplier_id = self._get_product_supplier_candidates()[:1]
        elif self.fulfillment_method == "supplier":
            self.source_warehouse_id = False
            self.internal_flow_state = "not_applicable"
            self.supplier_id = self._get_product_supplier_candidates()[:1]

    @api.depends(
        "fulfillment_method",
        "purchase_order_id",
        "purchase_order_id.picking_ids.state",
        "purchase_order_id.picking_ids.wm_qc_status",
        "purchase_order_id.picking_ids.picking_type_id.warehouse_id",
        "internal_flow_state",
        "internal_picking_id.state",
        "internal_picking_id.wm_qc_status",
    )
    def _compute_route_status_display(self):
        for line in self:
            status = _("Chưa khởi tạo")
            if line.fulfillment_method == "supplier":
                if line.purchase_order_id:
                    receipt_pickings = line.purchase_order_id.picking_ids.filtered(
                        lambda picking: picking.picking_type_code == "incoming"
                        and picking.picking_type_id.warehouse_id == line.request_warehouse_id
                    )
                    if receipt_pickings.filtered(lambda picking: picking.state == "done"):
                        status = _("Cửa hàng đã nhận hàng")
                    elif receipt_pickings.filtered(lambda picking: picking.wm_qc_status == "rejected"):
                        status = _("Hàng lỗi")
                    elif receipt_pickings:
                        status = _("Chờ cửa hàng nhận và QC")
                    else:
                        status = _("PO đã tạo")
                else:
                    status = _("Chờ tạo PO NCC")
            elif line.fulfillment_method == "supplier_central":
                if line.purchase_order_id:
                    receipt_pickings = line.purchase_order_id.picking_ids.filtered(
                        lambda picking: picking.picking_type_code == "incoming"
                        and picking.picking_type_id.warehouse_id
                        and getattr(picking.picking_type_id.warehouse_id, "mis_role", False) == "central"
                    )
                    if receipt_pickings.filtered(lambda picking: picking.wm_qc_status == "rejected"):
                        status = _("Kho tổng QC không đạt")
                    elif line.internal_picking_id and line.internal_picking_id.state == "done":
                        status = _("Cửa hàng đã nhận hàng")
                    elif line.internal_picking_id:
                        status = _("Chờ Kho tổng giao hàng")
                    elif line.internal_flow_state == "waiting_stock":
                        status = _("Kho tổng chưa đủ hàng để giao")
                    elif receipt_pickings.filtered(lambda picking: picking.state == "done"):
                        status = _("Kho tổng đã nhận, chờ kiểm hàng để giao")
                    elif receipt_pickings:
                        status = _("Chờ Kho tổng QC hàng NCC")
                    else:
                        status = _("PO đã tạo")
                else:
                    status = _("Chờ tạo PO NCC")
            elif line.fulfillment_method == "internal":
                if line.internal_picking_id and line.internal_picking_id.state == "done":
                    status = _("Cửa hàng đã nhận hàng")
                elif (
                    line.internal_flow_state == "rejected"
                    or (line.internal_picking_id and line.internal_picking_id.wm_qc_status == "rejected")
                ):
                    status = _("Hàng lỗi")
                elif line.internal_flow_state == "waiting_delivery":
                    status = _("Chờ Kho tổng giao hàng")
                elif line.internal_flow_state == "waiting_stock":
                    status = _("Kho tổng chưa đủ hàng để giao")
                elif line.internal_flow_state == "pending_check":
                    status = _("Chờ Kho tổng kiểm hàng để giao")
                elif line.internal_flow_state == "delivered":
                    status = _("Cửa hàng đã nhận hàng")
                else:
                    status = _("Chưa chuyển sang Kho tổng")
            line.route_status_display = status

    @api.depends(
        "product_id",
        "request_company_id",
        "request_warehouse_id",
        "source_warehouse_id",
    )
    def _compute_supply_metrics(self):
        quant_model = self.env["stock.quant"].sudo()
        for line in self:
            line.central_on_hand_qty = 0.0
            line.central_available_qty = 0.0
            line.other_warehouses_qty = 0.0
            line.source_available_qty = 0.0
            line.availability_breakdown = False
            if not line.product_id or not line.request_id:
                continue

            company_id = line.request_company_id.id
            warehouses = line.request_id._get_relevant_supply_warehouses().filtered(
                lambda wh: wh.company_id.id == company_id
            )
            breakdown = []
            for warehouse in warehouses:
                quants = quant_model.search(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("location_id", "child_of", warehouse.lot_stock_id.id),
                    ]
                )
                qty = sum(quants.mapped("quantity"))
                available = sum(quants.mapped("available_quantity"))
                line.central_on_hand_qty += qty
                line.central_available_qty += available
                if qty or available:
                    breakdown.append("%s: %.2f / %.2f" % (warehouse.display_name, qty, available))
                if line.source_warehouse_id and warehouse == line.source_warehouse_id:
                    line.source_available_qty = available
            line.availability_breakdown = " | ".join(breakdown)

    def action_view_supply_stock(self):
        self.ensure_one()
        warehouses = self.request_id._get_relevant_supply_warehouses()
        locations = warehouses.mapped("lot_stock_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Tồn kho tham chiếu"),
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "domain": [
                ("product_id", "=", self.product_id.id),
                ("location_id", "child_of", locations),
            ],
        }

    store_receipt_picking_id = fields.Many2one(
        "stock.picking",
        string="Store Receipt Picking",
        readonly=True,
        copy=False,
    )
    internal_flow_state = fields.Selection(
        [
            ("not_applicable", "Khong ap dung"),
            ("pending_check", "Cho Kho tong kiem"),
            ("ready_delivery", "\u0110\u1ee7 h\u00e0ng ch\u1edd giao"),
            ("waiting_receipt", "Cho NCC giao Kho tong"),
            ("waiting_stock", "Chua du hang"),
            ("waiting_delivery", "Cho Kho tong giao"),
            ("waiting_store_receipt", "Cho cua hang nhan"),
            ("rejected", "Hang loi"),
            ("delivered", "Da giao cua hang"),
        ],
        string="Tien trinh hau can",
        default="not_applicable",
        copy=False,
        tracking=True,
    )
    remaining_after_dispatch_qty = fields.Float(
        string="D\u1ef1 ki\u1ebfn c\u00f2n sau giao",
        compute="_compute_supply_metrics",
        digits="Product Unit of Measure",
    )
    stock_ready_to_dispatch = fields.Boolean(
        string="\u0110\u1ee7 h\u00e0ng giao",
        compute="_compute_supply_metrics",
    )

    @api.depends(
        "fulfillment_method",
        "purchase_order_id",
        "purchase_order_id.picking_ids.state",
        "purchase_order_id.picking_ids.wm_qc_status",
        "purchase_order_id.picking_ids.picking_type_id.warehouse_id",
        "internal_flow_state",
        "internal_picking_id.state",
        "internal_picking_id.wm_qc_status",
        "store_receipt_picking_id.state",
        "store_receipt_picking_id.wm_qc_status",
    )
    def _compute_route_status_display(self):
        for line in self:
            status = _("Chua khoi tao")
            if line.fulfillment_method == "supplier":
                if line.purchase_order_id:
                    receipt_pickings = line.purchase_order_id.picking_ids.filtered(
                        lambda picking: picking.picking_type_code == "incoming"
                        and picking.picking_type_id.warehouse_id == line.request_warehouse_id
                    )
                    if receipt_pickings.filtered(lambda picking: picking.state == "done"):
                        status = _("Cua hang da nhan hang")
                    elif receipt_pickings.filtered(lambda picking: picking.wm_qc_status == "rejected"):
                        status = _("Hang loi")
                    elif receipt_pickings:
                        status = _("Cho cua hang nhan va QC")
                    else:
                        status = _("PO da tao")
                else:
                    status = _("Cho tao PO NCC")
            elif line.fulfillment_method == "supplier_central":
                if line.purchase_order_id:
                    receipt_pickings = line.purchase_order_id.picking_ids.filtered(
                        lambda picking: picking.picking_type_code == "incoming"
                        and picking.picking_type_id.warehouse_id
                        and getattr(picking.picking_type_id.warehouse_id, "mis_role", False) == "central"
                    )
                    if receipt_pickings.filtered(lambda picking: picking.wm_qc_status == "rejected"):
                        status = _("Kho tong QC khong dat")
                    elif line.store_receipt_picking_id and line.store_receipt_picking_id.state == "done":
                        status = _("Cua hang da nhan hang")
                    elif line.store_receipt_picking_id and line.store_receipt_picking_id.wm_qc_status == "rejected":
                        status = _("Hang loi")
                    elif line.internal_flow_state == "waiting_store_receipt":
                        status = _("Cho cua hang nhan va QC")
                    elif line.internal_picking_id:
                        status = _("Cho Kho tong giao hang")
                    elif line.internal_flow_state == "ready_delivery":
                        status = _("\u0110\u1ee7 h\u00e0ng, ch\u1edd x\u00e1c nh\u1eadn giao")
                    elif line.internal_flow_state == "waiting_stock":
                        status = _("Kho tong chua du hang de giao")
                    elif receipt_pickings.filtered(lambda picking: picking.state == "done"):
                        status = _("Kho tong da nhan, cho kiem hang de giao")
                    elif receipt_pickings:
                        status = _("Cho Kho tong QC hang NCC")
                    else:
                        status = _("PO da tao")
                else:
                    status = _("Cho tao PO NCC")
            elif line.fulfillment_method == "internal":
                if line.store_receipt_picking_id and line.store_receipt_picking_id.state == "done":
                    status = _("Cua hang da nhan hang")
                elif (
                    line.internal_flow_state == "rejected"
                    or (line.internal_picking_id and line.internal_picking_id.wm_qc_status == "rejected")
                    or (line.store_receipt_picking_id and line.store_receipt_picking_id.wm_qc_status == "rejected")
                ):
                    status = _("Hang loi")
                elif line.internal_flow_state == "ready_delivery":
                    status = _("\u0110\u1ee7 h\u00e0ng, ch\u1edd x\u00e1c nh\u1eadn giao")
                elif line.internal_flow_state == "waiting_store_receipt":
                    status = _("Cho cua hang nhan va QC")
                elif line.internal_flow_state == "waiting_delivery":
                    status = _("Cho Kho tong giao hang")
                elif line.internal_flow_state == "waiting_stock":
                    status = _("Kho tong chua du hang de giao")
                elif line.internal_flow_state == "pending_check":
                    status = _("Cho Kho tong kiem hang de giao")
                elif line.internal_flow_state == "delivered":
                    status = _("Cua hang da nhan hang")
                else:
                    status = _("Chua chuyen sang Kho tong")
            line.route_status_display = status

    @api.depends(
        "product_id",
        "request_company_id",
        "request_warehouse_id",
        "source_warehouse_id",
        "approved_qty",
    )
    def _compute_supply_metrics(self):
        quant_model = self.env["stock.quant"].sudo()
        for line in self:
            line.central_on_hand_qty = 0.0
            line.central_available_qty = 0.0
            line.other_warehouses_qty = 0.0
            line.source_available_qty = 0.0
            line.remaining_after_dispatch_qty = 0.0
            line.stock_ready_to_dispatch = False
            line.availability_breakdown = False
            if not line.product_id or not line.request_id:
                continue

            company_id = line.request_company_id.id
            warehouses = line.request_id._get_relevant_supply_warehouses().filtered(
                lambda wh: wh.company_id.id == company_id
            )
            breakdown = []
            for warehouse in warehouses:
                quants = quant_model.search(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("location_id", "child_of", warehouse.lot_stock_id.id),
                    ]
                )
                qty = sum(quants.mapped("quantity"))
                available = sum(quants.mapped("available_quantity"))
                line.central_on_hand_qty += qty
                line.central_available_qty += available
                if qty or available:
                    breakdown.append("%s: %.2f / %.2f" % (warehouse.display_name, qty, available))
                if line.source_warehouse_id and warehouse == line.source_warehouse_id:
                    line.source_available_qty = available
            line.remaining_after_dispatch_qty = line.source_available_qty - line.approved_qty
            line.stock_ready_to_dispatch = line.source_available_qty >= line.approved_qty
            line.availability_breakdown = " | ".join(breakdown)
