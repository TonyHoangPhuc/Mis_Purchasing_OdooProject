from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

    wm_damage_note = fields.Char(
        string="Ghi chú lỗi",
        help="Mô tả ngắn tình trạng lỗi của lô hàng hoặc sản phẩm khi QC.",
    )
    wm_damaged_qty = fields.Float(
        string="Số lượng hư hỏng",
        digits="Product Unit of Measure",
        default=0.0,
        help="Số lượng hư hỏng được ghi nhận khi kiểm hàng nhập.",
    )
    wm_line_discrepancy_qty = fields.Float(
        string="Số lượng chênh lệch",
        compute="_compute_wm_line_discrepancy_qty",
        digits="Product Unit of Measure",
        help="Chênh lệch giữa số lượng dự kiến và số lượng thực nhận.",
    )

    @api.depends("product_uom_qty", "quantity")
    def _compute_wm_line_discrepancy_qty(self):
        for move in self:
            move.wm_line_discrepancy_qty = move.product_uom_qty - move.quantity

    @api.constrains("wm_damaged_qty", "quantity")
    def _check_wm_damaged_qty(self):
        for move in self:
            if move.wm_damaged_qty < 0:
                raise ValidationError("Số lượng hư hỏng phải lớn hơn hoặc bằng 0.")
            if move.quantity > 0 and move.wm_damaged_qty > move.quantity:
                raise ValidationError("Số lượng hư hỏng không được lớn hơn số lượng thực nhận.")
