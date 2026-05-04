from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


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
    wm_expected_qty = fields.Float(
        string="Số lượng dự kiến",
        digits="Product Unit of Measure",
        copy=False,
        help="Số lượng dự kiến tại thời điểm kiểm hàng. Giá trị này được giữ lại để hiển thị đúng sau QC.",
    )
    wm_line_discrepancy_qty = fields.Float(
        string="Số lượng chênh lệch",
        compute="_compute_wm_line_discrepancy_qty",
        digits="Product Unit of Measure",
        help="Chênh lệch giữa số lượng dự kiến và số lượng thực nhận.",
    )

    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute(
            """
            UPDATE stock_move
               SET wm_expected_qty = product_uom_qty
             WHERE wm_expected_qty IS NULL
                OR wm_expected_qty = 0
            """
        )
        return res

    def _get_wm_expected_qty(self):
        self.ensure_one()
        return self.wm_expected_qty if self.wm_expected_qty else self.product_uom_qty

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "wm_expected_qty" not in vals and "product_uom_qty" in vals:
                vals["wm_expected_qty"] = vals["product_uom_qty"]
        return super().create(vals_list)

    def _should_lock_wm_expected_qty(self):
        self.ensure_one()
        picking = self.picking_id
        return bool(
            picking
            and (
                getattr(picking, "store_actual_check_done", False)
                or picking.wm_qc_status in ("checking", "passed", "rejected")
                or picking.state in ("done", "cancel")
            )
        )

    def write(self, vals):
        if "product_uom_qty" in vals and "wm_expected_qty" not in vals:
            locked_moves = self.filtered(lambda move: move._should_lock_wm_expected_qty())
            unlocked_moves = self - locked_moves
            result = True
            if unlocked_moves:
                result = super(StockMove, unlocked_moves).write(
                    dict(vals, wm_expected_qty=vals["product_uom_qty"])
                ) and result
            if locked_moves:
                result = super(StockMove, locked_moves).write(vals) and result
            return result
        return super().write(vals)

    @api.depends("wm_expected_qty", "product_uom_qty", "quantity")
    def _compute_wm_line_discrepancy_qty(self):
        for move in self:
            move.wm_line_discrepancy_qty = move._get_wm_expected_qty() - move.quantity

    @api.constrains("wm_damaged_qty")
    def _check_wm_damaged_qty(self):
        for move in self:
            if move.wm_damaged_qty < 0:
                raise ValidationError("Số lượng hư hỏng phải lớn hơn hoặc bằng 0.")

    def _validate_wm_damaged_qty_not_over_received(self):
        for move in self:
            precision_rounding = move.product_uom.rounding or move.product_id.uom_id.rounding or 0.01
            if float_compare(
                move.wm_damaged_qty,
                move.quantity,
                precision_rounding=precision_rounding,
            ) > 0:
                raise ValidationError(
                    _("Số lượng hư hỏng không được lớn hơn số lượng thực nhận.")
                )
