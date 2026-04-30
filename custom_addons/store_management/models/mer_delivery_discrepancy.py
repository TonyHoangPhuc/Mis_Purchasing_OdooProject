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
    store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng",
        related="picking_id.location_dest_id.warehouse_id.store_record_id",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product", string="Sản phẩm", required=True
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

    @api.depends("expected_qty", "actual_qty")
    def _compute_discrepancy_qty(self):
        for rec in self:
            rec.discrepancy_qty = max(0.0, rec.actual_qty - rec.expected_qty)

    @api.depends("state", "central_stock_adjusted", "recovery_picking_id.state")
    def _compute_handling_status(self):
        for rec in self:
            if rec.state == "done":
                rec.handling_status = _("Đã thu hồi")
            elif rec.recovery_picking_id:
                rec.handling_status = _("Đang thu hồi")
            elif rec.central_stock_adjusted:
                rec.handling_status = _("Chờ Kho tổng thu hồi")
            elif rec.state == "reported":
                rec.handling_status = _("Chờ Merchandise duyệt")
            else:
                rec.handling_status = _("Chờ gửi")

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Mới")) == _("Mới"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("mer.excess.receipt")
                    or _("Mới")
                )
        return super().create(vals_list)

    def action_submit(self):
        self.ensure_one()
        if self.discrepancy_qty <= 0:
            raise UserError(_("Không có số lượng dư để báo cáo."))
        if self._is_central_to_store_excess():
            self._action_warehouse_adjust_logic()
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

            if rec._is_central_to_store_excess() or rec.picking_id.picking_type_code == "internal":
                self.env["stock.quant"].sudo()._update_available_quantity(
                    rec.product_id, source_location, -rec.discrepancy_qty
                )
            self.env["stock.quant"].sudo()._update_available_quantity(
                rec.product_id, excess_location, rec.discrepancy_qty
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
