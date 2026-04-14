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
    )
    internal_line_count = fields.Integer(
        string="Dòng nội bộ",
        compute="_compute_internal_flow_metrics",
    )
    pending_central_check_count = fields.Integer(
        string="Chờ Kho tổng kiểm",
        compute="_compute_internal_flow_metrics",
    )
    waiting_delivery_count = fields.Integer(
        string="Chờ Supply Chain giao",
        compute="_compute_internal_flow_metrics",
    )
    central_flow_status = fields.Char(
        string="Trạng thái Kho tổng",
        compute="_compute_internal_flow_metrics",
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

    @api.depends("line_ids.purchase_order_id", "line_ids.internal_picking_id")
    def _compute_document_counts(self):
        for request in self:
            request.purchase_order_count = len(request.line_ids.mapped("purchase_order_id"))
            request.internal_picking_count = len(request.line_ids.mapped("internal_picking_id"))

    @api.depends(
        "line_ids.fulfillment_method",
        "line_ids.internal_flow_state",
        "line_ids.internal_picking_id.state",
        "line_ids.internal_picking_id.wm_qc_status",
    )
    def _compute_internal_flow_metrics(self):
        for request in self:
            internal_lines = request.line_ids.filtered(lambda line: line.fulfillment_method == "internal")
            request.internal_line_count = len(internal_lines)
            request.pending_central_check_count = len(
                internal_lines.filtered(lambda line: line.internal_flow_state == "pending_check")
            )
            request.waiting_delivery_count = len(
                internal_lines.filtered(
                    lambda line: line.internal_flow_state == "waiting_delivery"
                    and line.internal_picking_id.state not in ("done", "cancel")
                )
            )
            has_rejected_line = any(
                line.internal_flow_state == "rejected"
                or (line.internal_picking_id and line.internal_picking_id.wm_qc_status == "rejected")
                for line in internal_lines
            )

            if not internal_lines:
                request.central_flow_status = _("Không có điều chuyển Kho tổng")
            elif request.pending_central_check_count:
                request.central_flow_status = _("Chờ Kho tổng kiểm hàng")
            elif request.waiting_delivery_count:
                request.central_flow_status = _("Chờ Supply Chain giao hàng")
            elif has_rejected_line:
                request.central_flow_status = _("Cửa hàng từ chối nhận do hàng lỗi")
            elif all(line.internal_flow_state == "delivered" for line in internal_lines):
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
                "|",
                ("mis_role", "in", ["central", "store"]),
                ("mis_role", "=", False),
            ]
        )
        return warehouses.filtered(lambda wh: wh.id != self.warehouse_id.id)

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
            if not request.line_ids:
                raise UserError(_("PR phải có ít nhất một sản phẩm trước khi trình quản lý."))
            for line in request.line_ids:
                if not line.fulfillment_method:
                    raise UserError(_("Vui lòng chọn phương án đáp ứng cho tất cả sản phẩm trước khi trình quản lý."))
                if line.fulfillment_method == "internal":
                    if not line.source_warehouse_id:
                        raise UserError(
                            _("Sản phẩm %s chưa chọn kho nguồn để điều chuyển nội bộ.")
                            % line.product_id.display_name
                        )
                elif line.fulfillment_method == "supplier" and not line.supplier_id:
                    raise UserError(_("Sản phẩm %s chưa có NCC đáp ứng.") % line.product_id.display_name)

    def _get_pending_internal_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.fulfillment_method == "internal"
            and line.internal_flow_state == "pending_check"
            and not line.internal_picking_id
        )

    def _is_line_logistically_completed(self, line):
        self.ensure_one()
        if line.fulfillment_method == "supplier":
            if not line.purchase_order_id:
                return False
            receipt_pickings = line.purchase_order_id.picking_ids.filtered(
                lambda picking: picking.state != "cancel"
                and picking.picking_type_code == "incoming"
                and picking.picking_type_id.warehouse_id == line.request_warehouse_id
            )
            return bool(
                receipt_pickings.filtered(
                    lambda picking: picking.state == "done" or picking.wm_qc_status == "rejected"
                )
            )

        if line.fulfillment_method == "internal":
            return line.internal_flow_state in ("delivered", "rejected")

        return False

    def _sync_state_with_logistics(self):
        active_states = {"approved", "po_created", "done"}
        for request in self.filtered(lambda req: req.state in active_states):
            lines = request.line_ids.filtered(lambda line: line.fulfillment_method in ("supplier", "internal"))
            if not lines:
                continue

            all_completed = all(request._is_line_logistically_completed(line) for line in lines)
            has_started_documents = any(line.purchase_order_id or line.internal_picking_id for line in lines)

            if all_completed:
                request.state = "done"
            elif has_started_documents:
                request.state = "po_created"

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
        if self.state != "approved":
            raise UserError(_("PR cần được phê duyệt trước khi khởi tạo xử lý."))

        lines_to_process = self.line_ids.filtered(
            lambda line: line.fulfillment_method and not line.purchase_order_id and not line.internal_picking_id
        )
        if not lines_to_process:
            raise UserError(_("Tất cả dòng sản phẩm của PR này đã được khởi tạo xử lý rồi."))

        created_orders = self.env["purchase.order"]
        supplier_groups = defaultdict(lambda: self.env["mer.purchase.request.line"])

        for line in lines_to_process:
            if line.fulfillment_method == "supplier":
                supplier_groups[line.supplier_id.id] |= line

        for supplier_id, grouped_lines in supplier_groups.items():
            supplier = self.env["res.partner"].browse(supplier_id)
            order = self.env["purchase.order"].sudo().create(
                {
                    "partner_id": supplier.id,
                    "origin": self.name,
                    "date_order": fields.Datetime.now(),
                    "picking_type_id": self.warehouse_id.in_type_id.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": line.product_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.product_qty,
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
            grouped_lines.with_context(store_skip_sync_rule=True).write({"purchase_order_id": order.id})
            created_orders |= order

        internal_lines = lines_to_process.filtered(lambda line: line.fulfillment_method == "internal")
        if internal_lines:
            internal_lines.with_context(store_skip_sync_rule=True).write({"internal_flow_state": "pending_check"})

        if created_orders:
            self.purchase_id = created_orders[0]
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
        pending_lines = self._get_pending_internal_lines()
        if not pending_lines:
            raise UserError(_("PR này không có dòng nội bộ nào đang chờ Kho tổng kiểm hàng."))

        insufficient_lines = pending_lines.filtered(lambda line: line.source_available_qty < line.product_qty)
        if insufficient_lines:
            raise UserError(
                _(
                    "Kho tổng chưa đủ hàng cho các sản phẩm: %s. "
                    "Theo quy trình hiện tại, không được giao thiếu nên PR sẽ tiếp tục ở trạng thái Chờ đủ hàng."
                )
                % ", ".join(insufficient_lines.mapped("product_id.display_name"))
            )

        grouped_lines = defaultdict(lambda: self.env["mer.purchase.request.line"])
        for line in pending_lines:
            grouped_lines[line.source_warehouse_id.id] |= line

        created_pickings = self.env["stock.picking"]
        for source_warehouse_id, lines in grouped_lines.items():
            source_warehouse = self.env["stock.warehouse"].browse(source_warehouse_id)
            picking = self.env["stock.picking"].sudo().create(
                {
                    "partner_id": self.store_id.partner_id.id if self.store_id and self.store_id.partner_id else False,
                    "picking_type_id": source_warehouse.int_type_id.id,
                    "location_id": source_warehouse.lot_stock_id.id,
                    "location_dest_id": self.warehouse_id.lot_stock_id.id,
                    "origin": self.name,
                    "scheduled_date": fields.Datetime.now(),
                    "move_ids": [
                        (
                            0,
                            0,
                            {
                                "description_picking": line.product_id.display_name,
                                "product_id": line.product_id.id,
                                "product_uom_qty": line.product_qty,
                                "product_uom": line.product_uom_id.id,
                                "location_id": source_warehouse.lot_stock_id.id,
                                "location_dest_id": self.warehouse_id.lot_stock_id.id,
                            },
                        )
                        for line in lines
                    ],
                }
            )
            picking.action_confirm()
            picking.action_assign()
            lines.with_context(store_skip_sync_rule=True).write(
                {
                    "internal_picking_id": picking.id,
                    "internal_flow_state": "waiting_delivery",
                }
            )
            created_pickings |= picking

        if created_pickings:
            self.state = "po_created"

        return {
            "type": "ir.actions.act_window",
            "res_model": "mer.purchase.request",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": dict(self.env.context, central_check_menu=1),
        }


class MerPurchaseRequestLine(models.Model):
    _inherit = "mer.purchase.request.line"

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
            ("internal", "Chuyển nội bộ"),
            ("supplier", "Nhập từ NCC"),
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
            ("waiting_delivery", "Chờ Supply Chain giao"),
            ("rejected", "Hàng lỗi"),
            ("delivered", "Đã giao cửa hàng"),
        ],
        string="Luồng nội bộ",
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

    @api.onchange("fulfillment_method", "product_id")
    def _onchange_fulfillment_method(self):
        if self.fulfillment_method == "internal":
            self.supplier_id = False
            self.source_warehouse_id = self.request_id._get_default_internal_source_warehouse()
            self.internal_flow_state = "not_applicable"
        elif self.fulfillment_method == "supplier":
            self.source_warehouse_id = False
            self.internal_flow_state = "not_applicable"
            self.supplier_id = self.product_id.seller_ids.mapped("partner_id").filtered(
                lambda partner: "NCC" in partner.category_id.mapped("name")
            )[:1]

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
                        lambda picking: picking.state != "cancel"
                        and picking.picking_type_code == "incoming"
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
            elif line.fulfillment_method == "internal":
                if line.internal_picking_id and line.internal_picking_id.state == "done":
                    status = _("Cửa hàng đã nhận hàng")
                elif (
                    line.internal_flow_state == "rejected"
                    or (line.internal_picking_id and line.internal_picking_id.wm_qc_status == "rejected")
                ):
                    status = _("Hàng lỗi")
                elif line.internal_flow_state == "waiting_delivery":
                    status = _("Chờ Supply Chain giao hàng")
                elif line.internal_flow_state == "pending_check":
                    status = _("Chờ Kho tổng kiểm hàng")
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
        warehouse_model = self.env["stock.warehouse"].sudo()
        for line in self:
            line.central_on_hand_qty = 0.0
            line.central_available_qty = 0.0
            line.other_warehouses_qty = 0.0
            line.source_available_qty = 0.0
            line.availability_breakdown = False
            if not line.product_id or not line.request_id:
                continue

            company_id = line.request_company_id.id
            request_wh = line.request_warehouse_id
            warehouses = warehouse_model.search(
                [
                    ("company_id", "=", company_id),
                    "|",
                    ("mis_role", "in", ["central", "store"]),
                    ("mis_role", "=", False),
                ]
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
                if warehouse.mis_role == "central":
                    line.central_on_hand_qty += qty
                    line.central_available_qty += available
                elif warehouse != request_wh:
                    line.other_warehouses_qty += qty
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
