import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MerExcessReceipt(models.Model):
    _name = "mer.excess.receipt"
    _description = "Báo cáo nhận dư hàng"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Mã báo cáo",
        copy=False,
        readonly=True,
        required=True,
        index=True,
        default=lambda self: _("Mới"),
    )
    picking_id = fields.Many2one(
        "stock.picking",
        string="Phiếu xuất/nhập kho gốc",
        required=True,
        domain="[('picking_type_code', 'in', ('incoming', 'internal'))]",
    )
    origin_request_id = fields.Many2one(
        "mer.purchase.request",
        string="PR gốc",
        compute="_compute_origin_request_id",
        readonly=True,
    )
    store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng",
        related="picking_id.location_dest_id.warehouse_id.store_record_id",
        store=True,
        readonly=True,
    )
    display_store_name = fields.Char(
        string="Cửa hàng hiển thị",
        compute="_compute_display_store_name",
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product", string="Sản phẩm", required=True
    )
    line_ids = fields.One2many(
        "mer.excess.receipt.line",
        "report_id",
        string="Chi tiết theo lô",
        copy=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lô hàng",
        readonly=True,
        copy=False,
    )
    expected_qty = fields.Float(string="SL Hệ thống")
    actual_qty = fields.Float(string="SL Thực tế", required=True)
    discrepancy_qty = fields.Float(
        string="SL Dư",
        compute="_compute_discrepancy_qty",
        store=True,
        readonly=True,
    )
    date_report = fields.Date(
        string="Ngày báo cáo", default=lambda self: fields.Date.context_today(self), required=True
    )
    notes = fields.Text(string="Ghi chú")
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("reported", "Chờ Merchandise duyệt"),
            ("approved", "Merchandise đã duyệt"),
            ("returning", "Đang thu hồi hàng"),
            ("done", "Hoàn tất"),
            ("cancel", "Đã hủy"),
        ],
        string="Trạng thái",
        default="draft",
        tracking=True,
    )

    recovery_picking_id = fields.Many2one(
        "stock.picking", string="Phiếu thu hồi", readonly=True
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
    source_location_id = fields.Many2one(
        "stock.location",
        string="Nguồn trừ tồn",
        readonly=True,
        copy=False,
    )
    holding_location_id = fields.Many2one(
        "stock.location",
        string="Vị trí hàng dư chờ thu hồi",
        readonly=True,
        copy=False,
    )
    central_stock_adjusted = fields.Boolean(
        string="Đã cập nhật tồn Kho tổng",
        readonly=True,
        copy=False,
    )
    handling_status = fields.Char(
        string="Tình trạng xử lý",
        compute="_compute_handling_status",
    )
    status_badge = fields.Selection(
        [
            ("new", "Mới"),
            ("done", "Hoàn tất"),
            ("cancel", "Đã hủy"),
        ],
        string="Trạng thái hiển thị",
        compute="_compute_status_badge",
    )

    @api.depends(
        "expected_qty",
        "actual_qty",
        "line_ids.expected_qty",
        "line_ids.actual_qty",
        "line_ids.discrepancy_qty",
    )
    def _compute_discrepancy_qty(self):
        for rec in self:
            if rec.line_ids:
                rec.discrepancy_qty = sum(rec.line_ids.mapped("discrepancy_qty"))
            else:
                rec.discrepancy_qty = max(0.0, rec.actual_qty - rec.expected_qty)

    @api.depends("picking_id", "picking_id.origin")
    def _compute_origin_request_id(self):
        request_model = self.env["mer.purchase.request"]
        for rec in self:
            request = rec.picking_id.mer_request_id if hasattr(rec.picking_id, "mer_request_id") else False
            if not request and rec.picking_id.origin:
                request = request_model.search([("name", "=", rec.picking_id.origin.split(" - ")[0])], limit=1)
            rec.origin_request_id = request

    @api.depends("picking_id", "picking_id.origin", "store_id", "source_route_type")
    def _compute_display_store_name(self):
        for rec in self:
            origin_request = rec.origin_request_id
            if origin_request.store_id:
                rec.display_store_name = origin_request.store_id.display_name
            elif rec.store_id:
                rec.display_store_name = rec.store_id.display_name
            elif rec.source_route_type == "supplier_to_central":
                rec.display_store_name = _("Kho tổng")
            else:
                rec.display_store_name = False

    @api.depends("state", "central_stock_adjusted", "recovery_picking_id.state")
    def _compute_handling_status(self):
        for rec in self:
            if rec.state == "cancel":
                rec.handling_status = _("Đã hủy")
            elif rec.state == "done":
                rec.handling_status = _("Đã thu hồi")
            elif rec.recovery_picking_id:
                rec.handling_status = _("Đã gửi Kho tổng")
            elif rec.state == "approved" or rec.central_stock_adjusted:
                rec.handling_status = _("Chờ Merchandise gửi Kho tổng")
            elif rec.state == "reported":
                rec.handling_status = _("Chờ Merchandise phê duyệt")
            else:
                rec.handling_status = _("Chờ Cửa hàng gửi Merchandise")

    @api.depends("state")
    def _compute_status_badge(self):
        for rec in self:
            if rec.state == "cancel":
                rec.status_badge = "cancel"
            elif rec.state == "done":
                rec.status_badge = "done"
            else:
                rec.status_badge = "new"

    def _is_central_to_store_excess(self):
        self.ensure_one()
        return bool(
            self.picking_id
            and self.picking_id.store_route_type == "central_to_store"
            and self.picking_id._is_store_receipt_for_qc()
        )

    def _get_central_source_location(self):
        self.ensure_one()
        if self.source_location_id:
            return self.source_location_id
        if self._is_central_to_store_excess():
            central_picking = self.picking_id._get_store_receipt_central_source_picking()
            if central_picking:
                return central_picking.location_id
        return self.picking_id.location_id

    def _get_holding_location(self):
        self.ensure_one()
        if self.holding_location_id:
            return self.holding_location_id
        if self._is_central_to_store_excess():
            return self.picking_id._get_or_create_store_excess_holding_location()

        parent_location = self.picking_id.location_dest_id
        excess_location = self.env["stock.location"].search([
            ("location_id", "=", parent_location.id),
            ("name", "=", "Hàng nhận dư (Chờ trả)")
        ], limit=1)

        if not excess_location:
            excess_location = self.env["stock.location"].create({
                "name": "Hàng nhận dư (Chờ trả)",
                "location_id": parent_location.id,
                "usage": "internal",
            })
        return excess_location

    @api.onchange("picking_id", "product_id")
    def _onchange_picking_product(self):
        if self.picking_id and self.product_id:
            move = self.picking_id.move_ids.filtered(lambda m: m.product_id == self.product_id)
            if move:
                self.expected_qty = sum(move.mapped("product_uom_qty"))
            else:
                self.expected_qty = 0.0
            self.lot_id = self._get_single_source_lot()
            if not self.line_ids:
                self.line_ids = [(5, 0, 0)] + [
                    (0, 0, line_vals)
                    for line_vals in self._prepare_default_line_values(
                        actual_qty=self.actual_qty or None,
                        expected_qty=self.expected_qty or None,
                    )
                ]
            self._apply_line_totals()

    @api.onchange(
        "line_ids",
        "line_ids.expected_qty",
        "line_ids.actual_qty",
        "line_ids.lot_id",
    )
    def _onchange_line_ids(self):
        self._apply_line_totals()

    def _get_single_source_lot(self):
        self.ensure_one()
        if self.line_ids:
            lots = self.line_ids.mapped("lot_id")
            distinct_lots = lots.filtered(bool)
            return distinct_lots[0] if len(distinct_lots) == 1 and len(self.line_ids) == 1 else False
        if not self.picking_id or not self.product_id:
            return False
        lots = self.picking_id.move_line_ids.filtered(
            lambda line: line.product_id == self.product_id and line.lot_id and line.quantity > 0
        ).mapped("lot_id")
        return lots[0] if len(lots) == 1 else False

    def _get_source_lot_breakdown(self):
        self.ensure_one()
        if not self.picking_id or not self.product_id:
            return []

        product_moves = self.picking_id.move_ids.filtered(
            lambda current_move: current_move.product_id == self.product_id
        )
        if not product_moves:
            return []

        breakdown = []
        for move in product_moves:
            move_expected_qty = move._get_wm_expected_qty()
            lot_lines = self.picking_id.move_line_ids.filtered(
                lambda line: line.move_id == move and line.lot_id
            ).sorted("id")
            if not lot_lines:
                breakdown.append(
                    {
                        "lot_id": False,
                        "expected_qty": move_expected_qty,
                    }
                )
                continue

            remaining_expected = move_expected_qty
            last_index = len(lot_lines) - 1
            for index, move_line in enumerate(lot_lines):
                if index == last_index:
                    expected_qty = max(remaining_expected, 0.0)
                else:
                    expected_qty = min(move_line.quantity, max(remaining_expected, 0.0))
                breakdown.append(
                    {
                        "lot_id": move_line.lot_id.id,
                        "expected_qty": expected_qty,
                    }
                )
                remaining_expected -= expected_qty
        return breakdown

    def _prepare_default_line_values(self, actual_qty=None, expected_qty=None):
        self.ensure_one()
        breakdown = self._get_source_lot_breakdown()
        if not breakdown:
            return []

        total_expected = expected_qty if expected_qty is not None else sum(
            item["expected_qty"] for item in breakdown
        )
        total_actual = actual_qty if actual_qty is not None else (
            self.actual_qty or total_expected
        )

        remaining_actual = max(total_actual, 0.0)
        line_values = []
        last_index = len(breakdown) - 1
        for index, item in enumerate(breakdown):
            line_expected = item["expected_qty"]
            if index == last_index:
                line_actual = max(remaining_actual, 0.0)
            else:
                line_actual = min(line_expected, max(remaining_actual, 0.0))
            line_values.append(
                {
                    "lot_id": item["lot_id"],
                    "expected_qty": line_expected,
                    "actual_qty": line_actual,
                }
            )
            remaining_actual -= line_actual
        return line_values

    def _apply_line_totals(self):
        for rec in self:
            if not rec.line_ids:
                continue
            rec.expected_qty = sum(rec.line_ids.mapped("expected_qty"))
            rec.actual_qty = sum(rec.line_ids.mapped("actual_qty"))
            distinct_lots = rec.line_ids.mapped("lot_id").filtered(bool)
            rec.lot_id = distinct_lots[0] if len(distinct_lots) == 1 and len(rec.line_ids) == 1 else False

    def _sync_stored_totals_from_lines(self):
        for rec in self.filtered("line_ids"):
            values = {
                "expected_qty": sum(rec.line_ids.mapped("expected_qty")),
                "actual_qty": sum(rec.line_ids.mapped("actual_qty")),
            }
            distinct_lots = rec.line_ids.mapped("lot_id").filtered(bool)
            values["lot_id"] = (
                distinct_lots[0].id
                if len(distinct_lots) == 1 and len(rec.line_ids) == 1
                else False
            )
            if (
                rec.expected_qty != values["expected_qty"]
                or rec.actual_qty != values["actual_qty"]
                or rec.lot_id.id != values["lot_id"]
            ):
                rec.with_context(skip_excess_line_sync=True).write(values)

    def _get_discrepancy_breakdown(self):
        self.ensure_one()
        if self.line_ids:
            breakdown = {}
            for line in self.line_ids.filtered(lambda current_line: current_line.discrepancy_qty > 0):
                key = line.lot_id.id or 0
                breakdown.setdefault(
                    key,
                    {
                        "lot": line.lot_id,
                        "qty": 0.0,
                    },
                )
                breakdown[key]["qty"] += line.discrepancy_qty
            if breakdown:
                return list(breakdown.values())

        lot = self.lot_id or self._get_single_source_lot()
        return [{"lot": lot, "qty": self.discrepancy_qty}] if self.discrepancy_qty > 0 else []

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Mới")) == _("Mới"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("mer.excess.receipt")
                    or _("Mới")
                )
            if vals.get("picking_id") and vals.get("product_id"):
                report = self.new(vals)
                if not vals.get("line_ids"):
                    default_line_values = report._prepare_default_line_values(
                        actual_qty=vals.get("actual_qty"),
                        expected_qty=vals.get("expected_qty"),
                    )
                    if default_line_values:
                        vals["line_ids"] = [(0, 0, line_vals) for line_vals in default_line_values]
                if not vals.get("lot_id"):
                    lot = report._get_single_source_lot()
                    if lot:
                        vals["lot_id"] = lot.id
        records = super().create(vals_list)
        records._sync_stored_totals_from_lines()
        return records

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_excess_line_sync"):
            return res
        if any(key in vals for key in ("line_ids", "picking_id", "product_id")):
            for rec in self:
                if not rec.line_ids and rec.picking_id and rec.product_id:
                    default_line_values = rec._prepare_default_line_values()
                    if default_line_values:
                        rec.with_context(skip_excess_line_sync=True).write(
                            {
                                "line_ids": [(5, 0, 0)]
                                + [(0, 0, line_vals) for line_vals in default_line_values]
                            }
                        )
        if any(key in vals for key in ("line_ids", "picking_id", "product_id", "expected_qty", "actual_qty")):
            self._sync_stored_totals_from_lines()
        return res

    def action_submit(self):
        self.ensure_one()
        if self.line_ids:
            self._sync_stored_totals_from_lines()
        # if self.product_id.tracking != "none" and self.line_ids.filtered(
        #     lambda line: line.actual_qty > 0 and not line.lot_id
        # ):
        #     raise UserError(_("Sản phẩm theo lô cần khai báo đầy đủ lot cho từng dòng nhận dư trước khi gửi Merchandise."))
        if self.discrepancy_qty <= 0:
            raise UserError(_("Không có số lượng dư để báo cáo."))
        self.state = "reported"
        self.message_post(body=_("Đã gửi báo cáo nhận dư hàng đến đội Merchandise."))

    def action_merchandise_approve(self):
        """Phê duyệt bởi Merchandise: Tự động trừ tồn kho Kho tổng, KHÔNG cộng vào Cửa hàng."""
        self.ensure_one()
        self._action_warehouse_adjust_logic()
        self.state = "approved"
        self.message_post(
            body=_(
                "Merchandise đã phê duyệt. Hệ thống đã tự động trừ tồn kho tại Kho Tổng để khớp thực tế giao thừa. "
                "Lưu ý: Tồn kho Cửa hàng KHÔNG thay đổi vì đây là hàng giữ hộ."
            )
        )

    def _action_warehouse_adjust_logic(self):
        """Dịch chuyển hàng dư từ Kho tổng sang địa điểm 'Chờ trả' của Cửa hàng."""
        for rec in self:
            if rec.discrepancy_qty <= 0:
                continue
            if rec.central_stock_adjusted:
                continue

            source_location = rec._get_central_source_location()
            excess_location = rec._get_holding_location()
            if not source_location or not excess_location:
                raise UserError(_("Không xác định được vị trí nguồn hoặc vị trí chờ thu hồi cho hàng dư."))

            discrepancy_breakdown = rec._get_discrepancy_breakdown()
            for item in discrepancy_breakdown:
                lot = item["lot"]
                qty = item["qty"]
                if rec._is_central_to_store_excess() or rec.picking_id.picking_type_code == "internal":
                    self.env["stock.quant"].sudo()._update_available_quantity(
                        rec.product_id, source_location, -qty, lot_id=lot
                    )
                self.env["stock.quant"].sudo()._update_available_quantity(
                    rec.product_id, excess_location, qty, lot_id=lot
                )
            rec.write(
                {
                    "source_location_id": source_location.id,
                    "holding_location_id": excess_location.id,
                    "central_stock_adjusted": True,
                }
            )

    def action_create_recovery_picking(self):
        """Tạo phiếu thu hồi hàng từ địa điểm 'Chờ trả' của Cửa hàng về Kho tổng."""
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Merchandise cần phê duyệt báo cáo nhận dư trước khi tạo đơn thu hồi."))
        if self.recovery_picking_id:
            raise UserError(_("Phiếu thu hồi đã được tạo."))

        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"),
            ("warehouse_id.mis_role", "=", "central"),
        ], limit=1)
        if not picking_type:
            raise UserError(_("Chưa cấu hình loại phiếu nội bộ cho Kho tổng để tạo đơn thu hồi."))

        excess_location = self._get_holding_location()
        if not excess_location:
            raise UserError(_("Không tìm thấy địa điểm hàng dư tại cửa hàng để thu hồi."))
        destination_location = self._get_central_source_location()
        if not destination_location:
            raise UserError(_("Không xác định được vị trí Kho tổng nhận hàng thu hồi."))
        discrepancy_breakdown = self._get_discrepancy_breakdown()
        picking_vals = {
            "picking_type_id": picking_type.id,
            "location_id": excess_location.id,
            "location_dest_id": destination_location.id,
            "origin": self.name,
            "move_ids": [
                (0, 0, {
                    "description_picking": _("Thu hồi hàng nhận dư"),
                    "product_id": self.product_id.id,
                    "product_uom_qty": self.discrepancy_qty,
                    "product_uom": self.product_id.uom_id.id,
                    "location_id": excess_location.id,
                    "location_dest_id": destination_location.id,
                })
            ],
        }
        picking = self.env["stock.picking"].create(picking_vals)
        picking.action_confirm()

        move = picking.move_ids[:1]
        if discrepancy_breakdown and move:
            picking.move_line_ids.unlink()
            for item in discrepancy_breakdown:
                move_line_vals = move._prepare_move_line_vals(quantity=item["qty"])
                move_line_vals.update(
                    {
                        "lot_id": item["lot"].id if item["lot"] else False,
                        "quantity": item["qty"],
                        "location_id": excess_location.id,
                        "location_dest_id": destination_location.id,
                    }
                )
                self.env["stock.move.line"].create(move_line_vals)

        self.recovery_picking_id = picking.id
        self.state = "returning"
        return True

    def action_done(self):
        """Xác nhận hoàn tất sau khi Kho tổng nhận lại hàng."""
        self.ensure_one()
        if self.recovery_picking_id and self.recovery_picking_id.state not in ("done", "cancel"):
            # Tự động điền số lượng và Validate phiếu thu hồi để tối ưu UX
            for move in self.recovery_picking_id.move_ids:
                move.quantity = move.product_uom_qty
            try:
                self.recovery_picking_id.with_context(
                    skip_backorder=True,
                    cancel_backorder=True,
                    picking_ids_not_to_backorder=self.recovery_picking_id.ids,
                ).button_validate()

            except Exception as e:
                error_msg = str(e)
                if "lô" in error_msg.lower() or "sê-ri" in error_msg.lower() or "lot" in error_msg.lower() or "serial" in error_msg.lower():
                    raise UserError(_(
                        "Sản phẩm này có quản lý theo Lô/Date (Lot/Serial).\n"
                        "Hệ thống không thể tự động nhận hàng vì cần bạn chỉ định chính xác mã Lô được thu hồi về.\n\n"
                        "HƯỚNG DẪN: Vui lòng click vào mã phiếu màu tím [%s] trên màn hình, sau đó nhập số Lô thủ công và bấm Xác nhận (Validate) tại phiếu đó."
                    ) % self.recovery_picking_id.name)
                raise UserError(_("Không thể tự động Validate phiếu thu hồi %s. Lỗi hệ thống: %s") % (self.recovery_picking_id.name, error_msg))
            
            if self.recovery_picking_id.state != "done":
                raise UserError(_("Phiếu thu hồi %s chưa được Validate hoàn tất. Vui lòng click vào mã phiếu để xử lý thủ công.") % self.recovery_picking_id.name)
        
        self.state = "done"


class MerExcessReceiptLine(models.Model):
    _name = "mer.excess.receipt.line"
    _description = "Chi tiết nhận dư theo lô"
    _order = "id"

    report_id = fields.Many2one(
        "mer.excess.receipt",
        string="Báo cáo",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        related="report_id.product_id",
        store=True,
        readonly=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lô hàng",
        domain="[('product_id', '=', product_id)]",
        readonly=True,
    )
    expected_qty = fields.Float(string="SL Hệ thống", required=True, readonly=True)
    actual_qty = fields.Float(string="SL Thực tế", required=True, readonly=True)
    discrepancy_qty = fields.Float(
        string="SL Dư",
        compute="_compute_discrepancy_qty",
        store=True,
        readonly=True,
    )

    @api.depends("expected_qty", "actual_qty")
    def _compute_discrepancy_qty(self):
        for rec in self:
            rec.discrepancy_qty = max(0.0, rec.actual_qty - rec.expected_qty)
