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

    @api.depends("expected_qty", "actual_qty")
    def _compute_discrepancy_qty(self):
        for rec in self:
            rec.discrepancy_qty = max(0.0, rec.actual_qty - rec.expected_qty)

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

            # 1. Tìm hoặc tạo địa điểm "Nhận dư (Chờ trả)" tại Cửa hàng
            parent_location = rec.picking_id.location_dest_id
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

            source_location = rec.picking_id.location_id

            # 2. Trừ tồn kho tại Kho tổng
            if rec.picking_id.picking_type_code == "internal":
                self.env["stock.quant"]._update_available_quantity(
                    rec.product_id, source_location, -rec.discrepancy_qty
                )
            
            # 3. Cộng tồn kho vào địa điểm "Chờ trả" của Cửa hàng
            self.env["stock.quant"]._update_available_quantity(
                rec.product_id, excess_location, rec.discrepancy_qty
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

        # Tìm địa điểm "Chờ trả" của cửa hàng
        parent_location = self.picking_id.location_dest_id
        excess_location = self.env["stock.location"].search([
            ("location_id", "=", parent_location.id),
            ("name", "=", "Hàng nhận dư (Chờ trả)")
        ], limit=1)

        if not excess_location:
            raise UserError(_("Không tìm thấy địa điểm hàng dư tại cửa hàng để thu hồi."))

        picking_vals = {
            "picking_type_id": picking_type.id,
            "location_id": excess_location.id,
            "location_dest_id": self.picking_id.location_id.id,
            "origin": self.name,
            "move_ids": [
                (0, 0, {
                    "name": _("Thu hồi hàng nhận dư từ %s: %s") % (self.store_id.name, self.name),
                    "product_id": self.product_id.id,
                    "product_uom_qty": self.discrepancy_qty,
                    "product_uom": self.product_id.uom_id.id,
                    "location_id": excess_location.id,
                    "location_dest_id": self.picking_id.location_id.id,
                })
            ],
        }
        picking_vals = {
            "picking_type_id": picking_type.id,
            "location_id": excess_location.id,
            "location_dest_id": self.picking_id.location_id.id,
            "origin": self.name,
            "move_ids": [
                (0, 0, {
                    "description_picking": "Thu hoi hang nhan du",
                    "product_id": self.product_id.id,
                    "product_uom_qty": self.discrepancy_qty,
                    "product_uom": self.product_id.uom_id.id,
                    "location_id": excess_location.id,
                    "location_dest_id": self.picking_id.location_id.id,
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
        if (
            self.recovery_picking_id
            and self.recovery_picking_id.state != "done"
        ):
            raise UserError(_("Phiếu thu hồi tại Kho tổng chưa được Validate hoàn tất."))
        self.state = "done"
