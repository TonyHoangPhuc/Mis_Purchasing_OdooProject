from odoo import api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    wm_qc_status = fields.Selection(
        [
            ("draft", "Nháp"),
            ("checking", "Đang kiểm tra"),
            ("passed", "Đạt"),
            ("rejected", "Không đạt"),
        ],
        string="Trạng thái QC",
        default="draft",
        copy=False,
        tracking=True,
    )
    wm_qc_checked_by = fields.Many2one(
        "res.users",
        string="Người kiểm QC",
        copy=False,
        readonly=True,
    )
    wm_qc_checked_on = fields.Datetime(
        string="Thời gian kiểm QC",
        copy=False,
        readonly=True,
    )
    wm_qc_note = fields.Text(string="Ghi chú QC")
    wm_expected_qty = fields.Float(
        string="Số lượng dự kiến",
        compute="_compute_wm_discrepancy_metrics",
        digits="Product Unit of Measure",
        store=True,
    )
    wm_received_qty = fields.Float(
        string="Số lượng thực nhận",
        compute="_compute_wm_discrepancy_metrics",
        digits="Product Unit of Measure",
        store=True,
    )
    wm_damaged_qty = fields.Float(
        string="Số lượng hư hỏng",
        compute="_compute_wm_discrepancy_metrics",
        digits="Product Unit of Measure",
        store=True,
    )
    wm_discrepancy_qty = fields.Float(
        string="Số lượng chênh lệch",
        compute="_compute_wm_discrepancy_metrics",
        digits="Product Unit of Measure",
        help="Số lượng dự kiến trừ số lượng thực nhận.",
        store=True,
    )
    wm_has_discrepancy = fields.Boolean(
        string="Có chênh lệch",
        compute="_compute_wm_discrepancy_metrics",
        store=True,
    )
    wm_is_incoming_receipt = fields.Boolean(
        string="Là phiếu nhập",
        compute="_compute_wm_is_incoming_receipt",
    )

    @api.depends("picking_type_code")
    def _compute_wm_is_incoming_receipt(self):
        for picking in self:
            picking.wm_is_incoming_receipt = picking.picking_type_code == "incoming"

    @api.depends(
        "move_ids",
        "move_ids.product_uom_qty",
        "move_ids.quantity",
        "move_ids.wm_damaged_qty",
        "move_ids.state",
    )
    def _compute_wm_discrepancy_metrics(self):
        for picking in self:
            relevant_moves = picking.move_ids.filtered(lambda move: move.state != "cancel")
            expected_qty = sum(relevant_moves.mapped("product_uom_qty"))
            received_qty = sum(relevant_moves.mapped("quantity"))
            damaged_qty = sum(relevant_moves.mapped("wm_damaged_qty"))
            discrepancy_qty = expected_qty - received_qty
            picking.wm_expected_qty = expected_qty
            picking.wm_received_qty = received_qty
            picking.wm_damaged_qty = damaged_qty
            picking.wm_discrepancy_qty = discrepancy_qty
            picking.wm_has_discrepancy = bool(discrepancy_qty or damaged_qty)

    def _check_wm_incoming_receipt(self):
        non_incoming = self.filtered(lambda picking: picking.picking_type_code != "incoming")
        if non_incoming:
            raise UserError("Chỉ phiếu nhập mới được thực hiện thao tác QC.")

    def action_start_qc(self):
        self._check_wm_incoming_receipt()
        for picking in self:
            if picking.state == "cancel":
                raise UserError("Không thể kiểm QC cho phiếu nhập đã hủy.")
            if picking.wm_qc_status != "draft":
                raise UserError("Chỉ có thể bắt đầu QC từ trạng thái Nháp.")
            picking.write({"wm_qc_status": "checking"})

    def action_qc_pass(self):
        self._check_wm_incoming_receipt()
        for picking in self:
            if picking.wm_qc_status != "checking":
                raise UserError("Chỉ phiếu đang kiểm tra mới có thể đánh dấu đạt.")
            if not picking.wm_received_qty:
                raise UserError("Cần nhập số lượng thực nhận trước khi xác nhận QC đạt.")
            picking.write(
                {
                    "wm_qc_status": "passed",
                    "wm_qc_checked_by": self.env.user.id,
                    "wm_qc_checked_on": fields.Datetime.now(),
                }
            )

    def action_qc_reject(self):
        self._check_wm_incoming_receipt()
        for picking in self:
            if picking.wm_qc_status != "checking":
                raise UserError("Chỉ phiếu đang kiểm tra mới có thể đánh dấu không đạt.")
            if not picking.wm_received_qty:
                raise UserError("Cần nhập số lượng thực nhận trước khi xác nhận QC không đạt.")
            picking.write(
                {
                    "wm_qc_status": "rejected",
                    "wm_qc_checked_by": self.env.user.id,
                    "wm_qc_checked_on": fields.Datetime.now(),
                }
            )
