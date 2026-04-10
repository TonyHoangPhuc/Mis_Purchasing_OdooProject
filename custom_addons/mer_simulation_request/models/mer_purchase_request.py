from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MerPurchaseRequestLine(models.Model):
    _name = "mer.purchase.request.line"
    _description = "Dòng yêu cầu mua Mer"
    _order = "request_id, id"

    request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yêu cầu",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        related="request_id.company_id",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Sản phẩm",
        required=True,
        domain="[('is_storable', '=', True)]",
    )
    name = fields.Char(
        string="Diễn giải",
        required=True,
        compute="_compute_name",
        store=True,
        readonly=False,
    )
    product_qty = fields.Float(
        string="Số lượng",
        required=True,
        default=1.0,
        digits="Product Unit of Measure",
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Đơn vị tính",
        required=True,
    )
    procurement_preference = fields.Selection(
        [
            ("auto", "Tự động"),
            ("purchase", "Mua ngoài"),
            ("internal", "Nội bộ"),
        ],
        string="Ưu tiên cung ứng",
        default="auto",
        required=True,
    )
    suggested_supply_method = fields.Selection(
        [
            ("purchase", "Mua ngoài"),
            ("internal", "Nội bộ"),
        ],
        string="Phương thức cung ứng đề xuất",
        compute="_compute_procurement_suggestion",
        store=True,
    )
    resolved_supply_method = fields.Selection(
        [
            ("purchase", "Mua ngoài"),
            ("internal", "Nội bộ"),
        ],
        string="Phương thức cung ứng áp dụng",
        compute="_compute_procurement_suggestion",
        store=True,
    )
    available_internal_qty = fields.Float(
        string="Số lượng nội bộ khả dụng",
        compute="_compute_procurement_suggestion",
        digits="Product Unit of Measure",
        store=True,
    )
    suggested_partner_id = fields.Many2one(
        "res.partner",
        string="Đối tác đề xuất",
        compute="_compute_procurement_suggestion",
        store=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Đối tác",
        help="Nhà cung cấp cho mua ngoài hoặc đối tác cửa hàng cho cấp nội bộ.",
    )
    can_fulfill_internally = fields.Boolean(
        string="Có thể đáp ứng nội bộ",
        compute="_compute_procurement_suggestion",
        store=True,
    )

    @api.depends("product_id")
    def _compute_name(self):
        for line in self:
            if not line.name and line.product_id:
                line.name = line.product_id.display_name

    @api.depends(
        "product_id",
        "product_qty",
        "procurement_preference",
        "request_id.allow_internal_fulfillment",
        "request_id.source_warehouse_id",
        "request_id.request_partner_id",
    )
    def _compute_procurement_suggestion(self):
        Quant = self.env["stock.quant"].sudo()
        for line in self:
            available_internal_qty = 0.0
            suggested_partner = False
            suggested_supply_method = "purchase"
            can_fulfill_internally = False

            if (
                line.product_id
                and line.request_id.source_warehouse_id
                and line.request_id.warehouse_id
                and line.request_id.source_warehouse_id != line.request_id.warehouse_id
            ):
                quants = Quant.search(
                    [
                        ("product_id", "=", line.product_id.id),
                        (
                            "location_id",
                            "child_of",
                            line.request_id.source_warehouse_id.lot_stock_id.id,
                        ),
                    ]
                )
                available_internal_qty = sum(quants.mapped("available_quantity"))
                can_fulfill_internally = available_internal_qty >= line.product_qty

            if line.request_id.allow_internal_fulfillment and can_fulfill_internally:
                suggested_supply_method = "internal"
                suggested_partner = line.request_id.request_partner_id or line.request_id.company_id.partner_id
            elif line.product_id.seller_ids:
                suggested_partner = line.product_id.seller_ids[:1].partner_id

            if line.procurement_preference == "purchase":
                resolved_supply_method = "purchase"
            elif line.procurement_preference == "internal":
                resolved_supply_method = "internal"
            else:
                resolved_supply_method = suggested_supply_method

            line.available_internal_qty = available_internal_qty
            line.can_fulfill_internally = can_fulfill_internally
            line.suggested_supply_method = suggested_supply_method
            line.resolved_supply_method = resolved_supply_method
            line.suggested_partner_id = suggested_partner

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            if not self.name:
                self.name = self.product_id.display_name

    @api.onchange("procurement_preference", "product_id", "product_qty")
    def _onchange_procurement_suggestion(self):
        if self.suggested_partner_id:
            self.partner_id = self.suggested_partner_id

    @api.constrains("product_qty")
    def _check_product_qty(self):
        for line in self:
            if line.product_qty <= 0:
                raise ValidationError("Requested quantity must be greater than 0.")

    @api.constrains("product_id", "product_uom_id")
    def _check_product_uom_id(self):
        for line in self:
            if not line.product_id or not line.product_uom_id:
                continue
            product_uom = line.product_id.uom_id
            if line.product_uom_id != product_uom and not line.product_uom_id._has_common_reference(product_uom):
                raise ValidationError(
                    _("Đơn vị tính của %s phải cùng hệ quy đổi với đơn vị tính của sản phẩm.")
                    % line.product_id.display_name
                )


class MerPurchaseRequest(models.Model):
    _name = "mer.purchase.request"
    _description = "Yêu cầu mua Mer"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Mã yêu cầu",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("submitted", "Đã gửi"),
            ("to_approve", "Chờ duyệt"),
            ("approved", "Đã duyệt"),
            ("po_created", "Đã tạo chứng từ cung ứng"),
            ("rejected", "Bị từ chối"),
            ("cancel", "Đã hủy"),
        ],
        string="Trạng thái",
        default="draft",
        tracking=True,
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Người yêu cầu",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    approver_id = fields.Many2one(
        "res.users",
        string="Người duyệt",
        readonly=True,
        tracking=True,
    )
    approval_date = fields.Datetime(
        string="Ngày duyệt",
        readonly=True,
    )
    date_request = fields.Date(
        string="Ngày yêu cầu",
        default=fields.Date.today,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Kho nhận",
        required=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    source_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Kho nguồn",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
        help="Used when the request is fulfilled internally through an allocation plan.",
    )
    request_partner_id = fields.Many2one(
        "res.partner",
        string="Cửa hàng/đối tác yêu cầu",
        tracking=True,
        help="Store partner used by supply chain allocation and priority logic.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp chính",
        tracking=True,
        help="Main vendor suggestion for the request. Individual lines can override it.",
    )
    allow_internal_fulfillment = fields.Boolean(
        string="Cho phép đáp ứng nội bộ",
        default=True,
        tracking=True,
    )
    note = fields.Text(string="Ghi chú")
    line_ids = fields.One2many(
        "mer.purchase.request.line",
        "request_id",
        string="Dòng yêu cầu",
        copy=True,
    )
    purchase_id = fields.Many2one(
        "purchase.order",
        string="Đơn mua chính",
        readonly=True,
        copy=False,
    )
    purchase_ids = fields.One2many(
        "purchase.order",
        "mer_request_id",
        string="Đơn mua",
        readonly=True,
    )
    allocation_plan_ids = fields.One2many(
        "supply.chain.allocation.plan",
        "mer_request_id",
        string="Kế hoạch phân bổ",
        readonly=True,
    )
    purchase_count = fields.Integer(
        string="Số đơn mua",
        compute="_compute_document_counts",
    )
    allocation_plan_count = fields.Integer(
        string="Số kế hoạch phân bổ",
        compute="_compute_document_counts",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("mer.purchase.request") or _("New")
        requests = super().create(vals_list)
        for request in requests:
            request.message_post(body=_("Đã tạo yêu cầu Mer."))
        return requests

    @api.depends("purchase_ids", "allocation_plan_ids")
    def _compute_document_counts(self):
        for request in self:
            request.purchase_count = len(request.purchase_ids)
            request.allocation_plan_count = len(request.allocation_plan_ids)

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        if self.warehouse_id and not self.request_partner_id:
            self.request_partner_id = self.company_id.partner_id
        if self.warehouse_id and not self.source_warehouse_id:
            other_warehouse = self.env["stock.warehouse"].search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("id", "!=", self.warehouse_id.id),
                ],
                limit=1,
            )
            self.source_warehouse_id = other_warehouse or self.warehouse_id

    @api.onchange("line_ids")
    def _onchange_line_ids(self):
        if self.partner_id or not self.line_ids:
            return
        purchase_lines = self.line_ids.filtered(
            lambda line: line.resolved_supply_method == "purchase" and line.suggested_partner_id
        )
        if purchase_lines:
            self.partner_id = purchase_lines[0].suggested_partner_id

    def _check_manager_rights(self):
        if not self.env.user.has_group("mer_simulation_request.group_mer_request_manager"):
            raise UserError("Chỉ quản lý Mer mới có thể duyệt hoặc từ chối yêu cầu.")

    def action_submit(self):
        for request in self:
            if not request.line_ids:
                raise UserError("Không thể gửi yêu cầu khi chưa có dòng hàng.")
            request.write({"state": "submitted"})
            request.message_post(
                body=_("Yêu cầu Mer đã được gửi bởi %s.") % request.requester_id.display_name
            )

    def action_send_to_manager(self):
        manager_group = self.env.ref("mer_simulation_request.group_mer_request_manager")
        for request in self:
            if request.state not in ("submitted", "draft"):
                raise UserError("Chỉ yêu cầu ở trạng thái nháp hoặc đã gửi mới có thể trình duyệt.")
            request.write({"state": "to_approve"})
            request.message_post(body=_("Yêu cầu Mer đã được trình quản lý duyệt."))
            manager_users = manager_group.user_ids.filtered(lambda user: user.partner_id)
            for user in manager_users:
                request.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=user.id,
                    summary=_("Duyệt yêu cầu Mer"),
                    note=_("Vui lòng xem và duyệt yêu cầu %s.") % request.name,
                )

    def action_approve(self):
        self._check_manager_rights()
        for request in self:
            if request.state != "to_approve":
                raise UserError("Chỉ yêu cầu đang chờ duyệt mới có thể được duyệt.")
            request.write(
                {
                    "state": "approved",
                    "approver_id": self.env.user.id,
                    "approval_date": fields.Datetime.now(),
                }
            )
            request.activity_unlink(["mail.mail_activity_data_todo"])
            request.message_post(body=_("Yêu cầu Mer đã được duyệt bởi %s.") % self.env.user.display_name)

    def action_reject(self):
        self._check_manager_rights()
        for request in self:
            if request.state not in ("submitted", "to_approve", "approved"):
                raise UserError("Chỉ yêu cầu đã gửi hoặc đang chờ duyệt mới có thể bị từ chối.")
            request.write({"state": "rejected"})
            request.activity_unlink(["mail.mail_activity_data_todo"])
            request.message_post(body=_("Yêu cầu Mer đã bị từ chối bởi %s.") % self.env.user.display_name)

    def action_draft(self):
        for request in self:
            if request.purchase_ids or request.allocation_plan_ids:
                raise UserError("Không thể đặt lại nháp sau khi đã tạo chứng từ cung ứng.")
            request.write({"state": "draft", "approver_id": False, "approval_date": False})
            request.message_post(body=_("Yêu cầu Mer đã được đặt lại về nháp."))

    def action_cancel(self):
        for request in self:
            request.write({"state": "cancel"})
            request.message_post(body=_("Yêu cầu Mer đã bị hủy."))

    def _resolve_purchase_partner(self, line):
        partner = line.partner_id or line.suggested_partner_id or self.partner_id
        if not partner:
            raise UserError(_("Không xác định được nhà cung cấp cho sản phẩm %s.") % line.product_id.display_name)
        return partner

    def _prepare_purchase_line_vals(self, line):
        return {
            "product_id": line.product_id.id,
            "name": line.name or line.product_id.display_name,
            "product_qty": line.product_qty,
            "product_uom_id": line.product_uom_id.id,
            "price_unit": line.product_id.standard_price,
            "date_planned": fields.Datetime.now(),
        }

    def _prepare_purchase_vals(self, vendor, lines):
        picking_type = self.warehouse_id.in_type_id
        return {
            "partner_id": vendor.id,
            "origin": self.name,
            "date_order": fields.Datetime.now(),
            "company_id": self.company_id.id,
            "picking_type_id": picking_type.id if picking_type else False,
            "mer_request_id": self.id,
            "order_line": [(0, 0, self._prepare_purchase_line_vals(line)) for line in lines],
        }

    def _prepare_allocation_plan_vals(self, lines):
        partner = self.request_partner_id or self.company_id.partner_id
        if not partner:
            raise UserError("Cần chọn cửa hàng/đối tác yêu cầu để phân bổ nội bộ.")
        if not self.source_warehouse_id:
            raise UserError("Cần chọn kho nguồn cho đáp ứng nội bộ.")
        if not self.warehouse_id:
            raise UserError("Cần chọn kho nhận cho đáp ứng nội bộ.")
        if self.source_warehouse_id == self.warehouse_id:
            raise UserError("Kho nguồn phải khác kho nhận.")
        return {
            "warehouse_id": self.source_warehouse_id.id,
            "source_location_id": self.source_warehouse_id.lot_stock_id.id,
            "picking_type_id": self.source_warehouse_id.int_type_id.id,
            "planned_date": fields.Datetime.now(),
            "state": "suggested",
            "note": _("Được tạo từ yêu cầu Mer %s.") % self.name,
            "mer_request_id": self.id,
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "partner_id": partner.id,
                        "destination_location_id": self.warehouse_id.lot_stock_id.id,
                        "product_id": line.product_id.id,
                        "priority": getattr(partner, "sc_store_priority", "medium") or "medium",
                        "on_hand_qty": line.available_internal_qty,
                        "demand_qty": line.product_qty,
                        "suggested_qty": line.product_qty,
                        "shortage_qty": max(line.product_qty - line.available_internal_qty, 0.0),
                    },
                )
                for line in lines
            ],
        }

    def _create_purchase_orders(self, lines):
        PurchaseOrder = self.env["purchase.order"].sudo()
        lines_by_vendor = defaultdict(lambda: self.env["mer.purchase.request.line"])
        for line in lines:
            vendor = self._resolve_purchase_partner(line)
            lines_by_vendor[vendor.id] |= line

        created_purchase_orders = self.env["purchase.order"]
        for vendor_id, vendor_lines in lines_by_vendor.items():
            vendor = self.env["res.partner"].browse(vendor_id)
            purchase_order = PurchaseOrder.create(self._prepare_purchase_vals(vendor, vendor_lines))
            purchase_order.button_confirm()
            purchase_order.message_post(body=_("Được tạo từ yêu cầu Mer %s.") % self.name)
            created_purchase_orders |= purchase_order
        return created_purchase_orders

    def _create_allocation_plan(self, lines):
        for line in lines:
            if line.available_internal_qty < line.product_qty:
                raise UserError(
                    _("Không đủ tồn nội bộ cho sản phẩm %s để đáp ứng yêu cầu %s.")
                    % (line.product_id.display_name, self.name)
                )

        allocation_plan = self.env["supply.chain.allocation.plan"].create(
            self._prepare_allocation_plan_vals(lines)
        )
        allocation_plan.message_post(body=_("Được tạo từ yêu cầu Mer %s.") % self.name)
        allocation_plan.action_create_internal_transfers()
        return allocation_plan

    def action_create_po(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError("Yêu cầu phải được duyệt trước khi tạo chứng từ cung ứng.")
        if not self.line_ids:
            raise UserError("Yêu cầu phải có ít nhất một dòng hàng.")

        purchase_lines = self.env["mer.purchase.request.line"]
        internal_lines = self.env["mer.purchase.request.line"]
        for line in self.line_ids:
            if line.resolved_supply_method == "internal" and self.allow_internal_fulfillment:
                internal_lines |= line
            else:
                purchase_lines |= line

        created_purchase_orders = self.env["purchase.order"]
        created_allocation_plan = self.env["supply.chain.allocation.plan"]
        if purchase_lines:
            created_purchase_orders = self._create_purchase_orders(purchase_lines)
        if internal_lines:
            created_allocation_plan = self._create_allocation_plan(internal_lines)

        if not created_purchase_orders and not created_allocation_plan:
            raise UserError("Không thể tạo chứng từ cung ứng từ yêu cầu này.")

        vals = {"state": "po_created"}
        if created_purchase_orders:
            vals["purchase_id"] = created_purchase_orders.sorted(key=lambda order: order.id)[0].id
        self.write(vals)

        message_parts = []
        if created_purchase_orders:
            message_parts.append(_("Đã tạo %s đơn mua.") % len(created_purchase_orders))
        if created_allocation_plan:
            message_parts.append(_("Đã tạo kế hoạch phân bổ %s.") % created_allocation_plan.display_name)
        self.message_post(body=" ".join(message_parts))

        if len(created_purchase_orders) == 1 and not created_allocation_plan:
            return {
                "type": "ir.actions.act_window",
                "res_model": "purchase.order",
                "res_id": created_purchase_orders.id,
                "view_mode": "form",
                "target": "current",
            }
        if created_allocation_plan and not created_purchase_orders:
            return {
                "type": "ir.actions.act_window",
                "res_model": "supply.chain.allocation.plan",
                "res_id": created_allocation_plan.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "res_model": "mer.purchase.request",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_form_action")
        action["domain"] = [("id", "in", self.purchase_ids.ids)]
        action["context"] = {"default_mer_request_id": self.id, "create": False}
        if len(self.purchase_ids) == 1:
            action["res_id"] = self.purchase_ids.id
            action["views"] = [(False, "form")]
        return action

    def action_view_allocation_plans(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "supply_chain_management.action_supply_chain_allocation_plans"
        )
        action["domain"] = [("id", "in", self.allocation_plan_ids.ids)]
        action["context"] = {"default_mer_request_id": self.id, "create": False}
        if len(self.allocation_plan_ids) == 1:
            action["res_id"] = self.allocation_plan_ids.id
            action["views"] = [(False, "form")]
        return action


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    mer_request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yêu cầu Mer",
        copy=False,
        index=True,
    )


class SupplyChainAllocationPlan(models.Model):
    _inherit = "supply.chain.allocation.plan"

    mer_request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yêu cầu Mer",
        copy=False,
        index=True,
    )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    mer_request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yêu cầu Mer",
        compute="_compute_mer_request_id",
        store=True,
        index=True,
    )

    @api.depends("purchase_id.mer_request_id", "scm_allocation_plan_id.mer_request_id")
    def _compute_mer_request_id(self):
        for picking in self:
            picking.mer_request_id = (
                picking.purchase_id.mer_request_id or picking.scm_allocation_plan_id.mer_request_id
            )
