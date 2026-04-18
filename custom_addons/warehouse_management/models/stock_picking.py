from odoo import _, api, fields, models
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

    @api.depends("purchase_id", "purchase_id.mer_request_id", "origin")
    def _compute_mer_request_id(self):
        raw_origins = {
            origin
            for origin in (self.mapped("origin") + self.mapped("purchase_id.origin"))
            if origin
        }
        origins = set(raw_origins)
        for origin in list(raw_origins):
            if " - " in origin:
                origins.add(origin.split(" - ", 1)[0].strip())
        requests_by_name = {}
        if origins:
            requests_by_name = {
                request.name: request
                for request in self.env["mer.purchase.request"].sudo().search([("name", "in", list(origins))])
            }

        for picking in self:
            request = picking.purchase_id.mer_request_id if picking.purchase_id else None
            if not request and picking.purchase_id and picking.purchase_id.origin:
                request = requests_by_name.get(picking.purchase_id.origin)
            if not request and picking.purchase_id and picking.purchase_id.origin and " - " in picking.purchase_id.origin:
                request = requests_by_name.get(picking.purchase_id.origin.split(" - ", 1)[0].strip())
            if not request and picking.origin:
                request = requests_by_name.get(picking.origin)
            if not request and picking.origin and " - " in picking.origin:
                request = requests_by_name.get(picking.origin.split(" - ", 1)[0].strip())
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

    def _is_wm_supplier_receipt(self):
        self.ensure_one()
        return bool(self.picking_type_code == "incoming" and self.partner_id)

    def _is_wm_internal_transfer(self):
        self.ensure_one()
        return self.picking_type_code == "internal"

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
        pickings_to_validate = self.env["stock.picking"]
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
            if picking.state not in ("done", "cancel"):
                pickings_to_validate |= picking
        if pickings_to_validate:
            res = pickings_to_validate.button_validate()
            # Tự động Hoàn tất PO nếu đã nhận đủ hàng
            for picking in pickings_to_validate:
                if picking.purchase_id and picking.state == 'done':
                    # Kiểm tra xem tất cả phiếu nhập của PO này đã xong chưa
                    incoming_pickings = picking.purchase_id.picking_ids.filtered(lambda p: p.picking_type_code == 'incoming')
                    if all(p.state in ['done', 'cancel'] for p in incoming_pickings):
                        picking.purchase_id.action_wm_lock_order()
            return res

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
            picking._action_process_qc_rejection()

    def _action_process_qc_rejection(self):
        """Nếu reject trước validate thì hủy phiếu để tồn kho không đổi."""
        self.ensure_one()
        if self.state != "done":
            self.action_cancel()
            self.message_post(
                body=_(
                    "QC không đạt. Phiếu đã được hủy trước khi nhập/xuất kho, vì vậy tồn kho không thay đổi."
                )
            )
            return False

        if self._is_wm_internal_transfer():
            return self._action_create_return_picking_to_origin()
        if self._is_wm_supplier_receipt():
            return self._action_create_return_picking_to_supplier()
        return False

    def _action_create_return_picking_to_supplier(self):
        """Tạo phiếu trả hàng về nhà cung cấp khi phiếu nhập hoàn tất bị reject."""
        self.ensure_one()
        damaged_moves = self.move_ids.filtered(lambda move: move.state != "cancel" and move.wm_damaged_qty > 0)
        if not damaged_moves:
            damaged_moves = self.move_ids.filtered(lambda move: move.state != "cancel" and move.quantity > 0)
        if not damaged_moves:
            return False

        return_location = self.location_id
        return_picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id", "=", self.picking_type_id.warehouse_id.id),
            ],
            limit=1,
        )
        if not return_picking_type:
            return False

        return_moves = []
        for move in damaged_moves:
            return_qty = move.wm_damaged_qty if move.wm_damaged_qty > 0 else move.quantity
            return_moves.append(
                (
                    0,
                    0,
                    {
                        "product_id": move.product_id.id,
                        "product_uom_qty": return_qty,
                        "product_uom": move.product_uom.id,
                        "location_id": self.location_dest_id.id,
                        "location_dest_id": return_location.id,
                        "description_picking": _("[TRẢ HÀNG LỖI] %s - QC không đạt từ phiếu %s")
                        % (move.product_id.display_name, self.name),
                    },
                )
            )

        if not return_moves:
            return False

        return_picking = self.env["stock.picking"].sudo().create(
            {
                "picking_type_id": return_picking_type.id,
                "partner_id": self.partner_id.id,
                "location_id": self.location_dest_id.id,
                "location_dest_id": return_location.id,
                "origin": _("Trả hàng lỗi QC: %s") % self.name,
                "move_ids": return_moves,
            }
        )
        return_picking.action_confirm()
        self.message_post(
            body=_(
                "QC không đạt. Đã tạo phiếu trả hàng <a href='#' data-oe-model='stock.picking' data-oe-id='%d'>%s</a> về nhà cung cấp."
            )
            % (return_picking.id, return_picking.name),
            subject=_("QC không đạt - Đã tạo phiếu trả hàng"),
        )
        return return_picking

    def _action_create_return_picking_to_origin(self):
        """Tạo phiếu hoàn trả nội bộ cho phiếu điều chuyển nội bộ đã hoàn tất."""
        self.ensure_one()
        destination_warehouse = self.location_dest_id.warehouse_id
        source_warehouse = self.location_id.warehouse_id
        if not destination_warehouse or not source_warehouse:
            return False

        return_moves = []
        for move in self.move_ids.filtered(lambda current_move: current_move.state != "cancel" and current_move.quantity > 0):
            return_moves.append(
                (
                    0,
                    0,
                    {
                        "product_id": move.product_id.id,
                        "product_uom_qty": move.quantity,
                        "product_uom": move.product_uom.id,
                        "location_id": destination_warehouse.lot_stock_id.id,
                        "location_dest_id": source_warehouse.lot_stock_id.id,
                        "description_picking": _("[HOÀN TRẢ NỘI BỘ] %s - Từ phiếu %s")
                        % (move.product_id.display_name, self.name),
                    },
                )
            )

        if not return_moves:
            return False

        return_picking = self.env["stock.picking"].sudo().create(
            {
                "partner_id": self.partner_id.id,
                "picking_type_id": destination_warehouse.int_type_id.id,
                "location_id": destination_warehouse.lot_stock_id.id,
                "location_dest_id": source_warehouse.lot_stock_id.id,
                "origin": _("Hoàn trả nội bộ QC: %s") % self.name,
                "move_ids": return_moves,
            }
        )
        return_picking.action_confirm()
        self.message_post(
            body=_(
                "QC không đạt. Đã tạo phiếu hoàn trả nội bộ <a href='#' data-oe-model='stock.picking' data-oe-id='%d'>%s</a>."
            )
            % (return_picking.id, return_picking.name),
            subject=_("QC không đạt - Đã tạo phiếu hoàn trả nội bộ"),
        )
        return return_picking
