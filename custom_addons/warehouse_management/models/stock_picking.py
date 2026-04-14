from odoo import api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    mer_request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yêu cầu Merchandise",
        compute="_compute_mer_request_id",
        compute_sudo=True,
    )

    wm_qc_status = fields.Selection(
        [
            ("draft", "Nháp"),
            ("checking", "Đang kiểm tra"),
            ("passed", "Đạt"),
            ("rejected", "Hàng lỗi"),
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

    @api.depends("purchase_id", "purchase_id.origin", "origin")
    def _compute_mer_request_id(self):
        requests_by_purchase = {}
        purchase_ids = self.mapped("purchase_id").ids
        if purchase_ids:
            purchase_requests = self.env["mer.purchase.request"].sudo().search([("purchase_id", "in", purchase_ids)])
            requests_by_purchase = {
                request.purchase_id.id: request
                for request in purchase_requests
                if request.purchase_id
            }

        origins = {
            origin
            for origin in (
                self.mapped("origin") + self.mapped("purchase_id.origin")
            )
            if origin
        }
        requests_by_name = {}
        if origins:
            requests_by_name = {
                request.name: request
                for request in self.env["mer.purchase.request"].sudo().search([("name", "in", list(origins))])
            }

        for picking in self:
            request = requests_by_purchase.get(picking.purchase_id.id)
            if not request and picking.purchase_id.origin:
                request = requests_by_name.get(picking.purchase_id.origin)
            if not request and picking.origin:
                request = requests_by_name.get(picking.origin)
            picking.mer_request_id = request

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

    def _has_wm_qc_issue_note(self):
        self.ensure_one()
        return bool(self.wm_qc_note or any(move.wm_damage_note for move in self.move_ids))

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
                raise UserError("Chỉ phiếu đang kiểm tra mới có thể đánh dấu hàng lỗi.")
            if not picking._has_wm_qc_issue_note():
                raise UserError("Cần nhập ghi chú lỗi trước khi xác nhận lô hàng không đạt.")
            picking.write(
                {
                    "wm_qc_status": "rejected",
                    "wm_qc_checked_by": self.env.user.id,
                    "wm_qc_checked_on": fields.Datetime.now(),
                }
            )
