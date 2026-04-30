from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MerPurchaseRequest(models.Model):
    _inherit = "mer.purchase.request"

    _store_blocking_states = ("draft", "submitted", "to_approve", "approved", "po_created")

    store_id = fields.Many2one("store.store", string="Cửa hàng yêu cầu", tracking=True)
    state = fields.Selection([
        ("draft", "Nháp"),
        ("submitted", "Đã gửi (Chờ xử lý)"),
        ("to_approve", "Chờ Quản lý duyệt"),
        ("approved", "Được phê duyệt"),
        ("po_created", "Đang thực hiện"),
        ("done", "Hoàn tất"),
        ("rejected", "Từ chối"),
        ("cancel", "Hủy"),
    ], string="Trạng thái", default="draft", tracking=True)

    # Các trường đếm và hiển thị trạng thái xử lý tại Kho tổng
    internal_picking_count = fields.Integer(string="Phiếu điều chuyển", compute="_compute_document_counts")
    purchase_order_count = fields.Integer(string="PO", compute="_compute_document_counts")
    can_create_processing = fields.Boolean(string="Can Create Processing", compute="_compute_document_counts")
    internal_line_count = fields.Integer(string="Dòng nội bộ", compute="_compute_internal_flow_metrics", store=True)
    ready_delivery_count = fields.Integer(string="Đủ hàng chờ giao", compute="_compute_internal_flow_metrics", store=True)
    pending_central_check_count = fields.Integer(string="Chờ Kho tổng kiểm", compute="_compute_internal_flow_metrics", store=True)
    insufficient_stock_count = fields.Integer(string="Chưa đủ hàng", compute="_compute_internal_flow_metrics", store=True)
    waiting_delivery_count = fields.Integer(string="Chờ giao hàng", compute="_compute_internal_flow_metrics", store=True)
    central_flow_status = fields.Selection([
        ('no_central', 'Không qua Kho tổng'),
        ('mixed', 'Hỗn hợp: Chờ NCC & Chờ kiểm'),
        ('insufficient', 'Kho tổng chưa đủ hàng'),
        ('pending_check', 'Chờ Kho tổng kiểm hàng'),
        ('ready_delivery', 'Đủ hàng, chờ xác nhận giao'),
        ('waiting_receipt', 'Chờ NCC giao Kho tổng'),
        ('waiting_delivery', 'Đang chờ giao'),
        ('done', 'Hoàn tất giao hàng'),
        ('processing', 'Đang xử lý'),
    ], string="Trạng thái Kho tổng", compute="_compute_internal_flow_metrics", store=True)

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
                    raise UserError(_("Cửa hàng này đã có PR %(pr)s đang xử lý cho sản phẩm đã chọn.") % {"pr": duplicate_request.name})
        return super().create(vals_list)

    def _extract_product_ids_from_line_commands(self, commands):
        product_ids = set()
        for command in commands or []:
            if isinstance(command, (list, tuple)) and len(command) >= 3 and command[0] == 0:
                product_ids.add(command[2].get("product_id"))
        return list(product_ids)

    def _find_duplicate_store_request(self, store_id, product_ids, exclude_request_id=None):
        domain = [("store_id", "=", store_id), ("state", "in", list(self._store_blocking_states)), ("line_ids.product_id", "in", product_ids)]
        if exclude_request_id:
            domain.append(("id", "!=", exclude_request_id))
        return self.search(domain, limit=1)

    def _check_store_menu_action_allowed(self, allowed_methods=None):
        allowed_methods = allowed_methods or set()
        if self.env.context.get("from_store_menu") and self.env.user.has_group("store_management.group_store_user"):
            if self.env.context.get("store_current_action") not in allowed_methods:
                raise UserError(_("Từ menu Cửa hàng, bạn chỉ được tạo PR, gửi PR và theo dõi trạng thái xử lý."))

    @api.depends("line_ids.fulfillment_method", "line_ids.purchase_order_id", "line_ids.internal_picking_id")
    def _compute_document_counts(self):
        for request in self:
            request.purchase_order_count = len(request.line_ids.mapped("purchase_order_id"))
            request.internal_picking_count = len(request.line_ids.mapped("internal_picking_id"))
            # Nút khởi tạo sẽ ẩn nếu tất cả các dòng đã được xử lý (đã có PO hoặc đã chuyển sang chờ kho kiểm)
            request.can_create_processing = bool(request.line_ids.filtered(lambda l: 
                l.approved_qty > 0 and not l.product_id.x_mer_stop_ordering and (
                    (l.fulfillment_method in ('supplier', 'supplier_central') and not l.purchase_order_id) or
                    (l.fulfillment_method == 'internal' and l.internal_flow_state == 'not_applicable')
                )
            ))
            request.internal_line_count = len(request.line_ids.filtered(lambda l: l.fulfillment_method in ('internal', 'supplier_central')))

    @api.depends(
        "line_ids.fulfillment_method", "line_ids.internal_flow_state", "line_ids.approved_qty",
        "line_ids.purchase_order_id.picking_ids.state", "line_ids.internal_picking_id.state"
    )
    def _compute_internal_flow_metrics(self):
        for request in self:
            internal_lines = request.line_ids.filtered(lambda l: l.fulfillment_method in ("internal", "supplier_central"))
            request.internal_line_count = len(internal_lines)
            request.pending_central_check_count = len(internal_lines.filtered(lambda l: l.internal_flow_state == "pending_check" and l.approved_qty > 0))
            request.ready_delivery_count = len(internal_lines.filtered(lambda l: l.internal_flow_state == "ready_delivery" and l.approved_qty > 0))
            request.insufficient_stock_count = len(internal_lines.filtered(lambda l: l.internal_flow_state == "waiting_stock" and l.approved_qty > 0))
            request.waiting_delivery_count = len(internal_lines.filtered(lambda l: l.internal_flow_state == "waiting_delivery"))
            
            if not internal_lines:
                request.central_flow_status = "no_central"
            elif any(l.internal_flow_state == "waiting_receipt" for l in internal_lines) and any(l.internal_flow_state == "pending_check" for l in internal_lines):
                request.central_flow_status = "mixed"
            elif request.insufficient_stock_count:
                request.central_flow_status = "insufficient"
            elif request.pending_central_check_count:
                request.central_flow_status = "pending_check"
            elif request.ready_delivery_count:
                request.central_flow_status = "ready_delivery"
            elif any(l.internal_flow_state == "waiting_receipt" for l in internal_lines):
                request.central_flow_status = "waiting_receipt"
            elif request.waiting_delivery_count:
                request.central_flow_status = "waiting_delivery"
            elif all(request._is_line_logistically_completed(l) for l in internal_lines):
                request.central_flow_status = "done"
            else:
                request.central_flow_status = "processing"

    def _is_line_logistically_completed(self, line):
        if line.internal_flow_state == 'overstock':
            return True
        if line.fulfillment_method == "supplier":
            # Phải nhận hàng xong tại cửa hàng (Picking của PO phải Done)
            if not line.purchase_order_id: return False
            return any(p.state == 'done' for p in line.purchase_order_id.picking_ids)
        if line.fulfillment_method == "supplier_central":
            # Phải nhận hàng xong tại kho tổng (Internal flow state đã được sync thành delivered)
            return line.internal_flow_state == "delivered"
        if line.fulfillment_method == "internal":
            return line.internal_flow_state == "delivered"
        return False

    def _sync_state_with_logistics(self):
        for request in self:
            for line in request.line_ids:
                if line.fulfillment_method == 'internal' and line.internal_picking_id:
                    # Kiểm tra chuỗi phiếu chuyển: Phải đợi phiếu nhập cuối cùng tại Cửa hàng Done
                    all_pickings = self.env['stock.picking'].search([('mer_request_id', '=', request.id)])
                    store_pickings = all_pickings.filtered(lambda p: p.picking_type_id.warehouse_id.mis_role == 'store' and p.picking_type_code == 'incoming')
                    
                    if store_pickings and all(p.state == 'done' for p in store_pickings):
                        line.internal_flow_state = 'delivered'
                    elif any(p.state == 'cancel' for p in all_pickings):
                        line.internal_flow_state = 'rejected'
                    else:
                        line.internal_flow_state = 'waiting_receipt'
                
                elif line.fulfillment_method == 'supplier' and line.purchase_order_id:
                    # NCC giao thẳng cửa hàng: Phải nhận xong tại cửa hàng
                    if any(p.state == 'done' for p in line.purchase_order_id.picking_ids):
                        line.internal_flow_state = 'delivered'

                elif line.fulfillment_method == 'supplier_central' and line.purchase_order_id:
                    # NCC giao về kho tổng: Phải nhận xong tại kho tổng
                    pickings = line.purchase_order_id.picking_ids.filtered(lambda p: p.picking_type_code == 'incoming')
                    if any(p.state == 'done' for p in pickings):
                        line.internal_flow_state = 'delivered'
            
            # Cập nhật trạng thái tổng quát của PR
            if all(request._is_line_logistically_completed(l) for l in request.line_ids):
                # Nếu tất cả các dòng đều bị từ chối/dừng đặt hàng thì chuyển sang Cancel
                if all(l.internal_flow_state in ('rejected', 'overstock') for l in request.line_ids):
                    request.state = 'cancel'
                else:
                    request.state = 'done'

    def _validate_merchandise_processing(self):
        for line in self.line_ids.filtered(lambda l: l.approved_qty > 0 and not l.product_id.x_mer_stop_ordering):
            if not line.fulfillment_method:
                raise UserError(_("Vui lòng chọn phương án đáp ứng cho %s.") % line.product_id.display_name)
            
            if line.fulfillment_method in ('supplier', 'supplier_central') and not line.supplier_id:
                raise UserError(_("Vui lòng chọn Nhà cung cấp cho sản phẩm %s.") % line.product_id.display_name)
            
            if line.fulfillment_method == 'internal' and not line.source_warehouse_id:
                # Nếu chưa chọn kho nguồn, tự động tìm kho tổng mặc định
                source_wh = self.env['stock.warehouse'].search([('mis_role', '=', 'central')], limit=1)
                if not source_wh:
                    raise UserError(_("Không tìm thấy Kho tổng nào để điều chuyển cho sản phẩm %s.") % line.product_id.display_name)
                line.source_warehouse_id = source_wh

    def _create_internal_pickings_for_lines(self, lines):
        lines = lines.filtered(lambda l: l.fulfillment_method == "internal" and not l.internal_picking_id and l.approved_qty > 0 and not l.product_id.x_mer_stop_ordering)
        if not lines: return self.env["stock.picking"]
        
        created_pickings = self.env["stock.picking"]
        for line in lines:
            source_wh = line.source_warehouse_id or self.env['stock.warehouse'].search([('mis_role','=','central')], limit=1)
            picking = self.env["stock.picking"].sudo().create({
                "mer_request_id": self.id,
                "picking_type_id": source_wh.out_type_id.id,
                "location_id": source_wh.lot_stock_id.id,
                "location_dest_id": self.warehouse_id.lot_stock_id.id,
                "origin": self.name,
                "move_ids": [(0, 0, {
                    "product_id": line.product_id.id, 
                    "product_uom_qty": line.approved_qty, 
                    "product_uom": line.product_uom_id.id, 
                    "location_id": source_wh.lot_stock_id.id, 
                    "location_dest_id": self.warehouse_id.lot_stock_id.id
                })]
            })
            picking.action_confirm()
            line.write({"internal_picking_id": picking.id, "internal_flow_state": "waiting_delivery"})
            created_pickings |= picking
        self.state = "po_created"
        return created_pickings

    def action_submit(self):
        self = self.with_context(store_current_action="action_submit")
        self._check_store_menu_action_allowed({"action_submit"})
        return super().action_submit()

    def action_send_to_manager(self):
        self = self.with_context(store_current_action="action_send_to_manager")
        self._check_store_menu_action_allowed({"action_send_to_manager"})
        valid_requests = self.env['mer.purchase.request']
        for request in self:
            # Tự động điền SL duyệt = SL yêu cầu nếu đang để trống hoặc bằng 0
            for line in request.line_ids.filtered(lambda l: l.approved_qty <= 0 and not l.product_id.x_mer_stop_ordering):
                line.approved_qty = line.product_qty
                
            stopped_lines = request.line_ids.filtered(lambda l: l.product_id.x_mer_stop_ordering and l.approved_qty > 0)
            if stopped_lines:
                stopped_lines.write({'approved_qty': 0.0, 'internal_flow_state': 'overstock'})
            
            if request.line_ids.filtered(lambda l: l.approved_qty > 0):
                valid_requests |= request
        if not valid_requests: raise UserError(_("Không có sản phẩm nào hợp lệ để trình duyệt (Tất cả đều bằng 0 hoặc đã dừng đặt hàng)."))
        valid_requests._validate_merchandise_processing()
        return super(MerPurchaseRequest, valid_requests).action_send_to_manager()

    def action_approve(self): return super().action_approve()
    def action_reject(self): return super().action_reject()
    def action_draft(self):
        self = self.with_context(store_current_action="action_draft")
        self._check_store_menu_action_allowed({"action_draft"})
        return super().action_draft()
    def action_cancel(self):
        self = self.with_context(store_current_action="action_cancel")
        self._check_store_menu_action_allowed({"action_cancel"})
        return super().action_cancel()

    def action_create_po(self):
        self = self.with_context(store_current_action="action_create_po")
        self._check_store_menu_action_allowed()
        for request in self:
            # Lọc các dòng hợp lệ (Số lượng duyệt > 0 và sản phẩm không bị dừng đặt hàng)
            active_lines = request.line_ids.filtered(lambda l: l.approved_qty > 0 and not l.product_id.x_mer_stop_ordering)
            
            if not active_lines:
                request.action_cancel()
                request.message_post(body=_("Yêu cầu đã tự động bị hủy do tất cả sản phẩm đều đã dừng đặt hàng hoặc số lượng duyệt bằng 0."))
                continue

            # Xử lý các dòng mua hàng từ NCC
            supplier_lines = active_lines.filtered(lambda l: l.fulfillment_method in ('supplier', 'supplier_central') and not l.purchase_order_id)
            for line in supplier_lines:
                target_wh = self.env['stock.warehouse'].search([('mis_role','=','central')], limit=1) if line.fulfillment_method == 'supplier_central' else request.warehouse_id
                po = self.env['purchase.order'].sudo().create({
                    'partner_id': line.supplier_id.id,
                    'picking_type_id': target_wh.in_type_id.id,
                    'order_line': [(0, 0, {'product_id': line.product_id.id, 'product_qty': line.approved_qty, 'price_unit': line.price_unit, 'date_planned': fields.Datetime.now()})]
                })
                po.button_confirm()
                # Liên kết PR vào Picking để hiện nút QC
                for picking in po.picking_ids:
                    picking.mer_request_id = request.id
                line.write({'purchase_order_id': po.id, 'internal_flow_state': 'waiting_receipt' if line.fulfillment_method == 'supplier_central' else 'not_applicable'})
            
            # Xử lý các dòng lấy từ Kho tổng có sẵn
            internal_lines = active_lines.filtered(lambda l: l.fulfillment_method == 'internal' and l.internal_flow_state == 'not_applicable')
            if internal_lines:
                internal_lines.write({'internal_flow_state': 'pending_check'})
                
            request.state = 'po_created'
            
            # Thông báo nếu có dòng bị bỏ qua
            stopped_lines = request.line_ids.filtered(lambda l: l.approved_qty > 0 and l.product_id.x_mer_stop_ordering)
            if stopped_lines:
                request.message_post(body=_("Lưu ý: Một số sản phẩm đã bị bỏ qua khi tạo PO/Điều chuyển do đang dừng đặt hàng: %s") % ", ".join(stopped_lines.mapped('product_id.name')))
        return True

    def action_confirm_central_stock(self):
        for request in self:
            request.line_ids.action_confirm_central_stock()
        return True

    def action_confirm_central_stock_ready(self):
        for request in self:
            request.line_ids.action_confirm_central_stock_ready()
        return True



class MerPurchaseRequestLine(models.Model):
    _inherit = "mer.purchase.request.line"

    approved_qty = fields.Float(string="Số lượng duyệt", digits="Product Unit of Measure")
    product_uom_id = fields.Many2one("uom.uom", string="Đơn vị", related="product_id.uom_id", readonly=True)
    price_unit = fields.Float(string="Đơn giá", related="product_id.list_price", readonly=True)
    
    internal_flow_state = fields.Selection([
        ("not_applicable", "Không áp dụng"),
        ("pending_check", "Chờ Kho tổng kiểm"),
        ("ready_delivery", "Đủ hàng chờ giao"),
        ("waiting_receipt", "Chờ NCC giao Kho tổng"),
        ("waiting_stock", "Chưa đủ hàng"),
        ("waiting_delivery", "Chờ giao"),
        ("waiting_store_receipt", "Chờ cửa hàng nhận"),
        ("rejected", "Hàng lỗi"),
        ("overstock", "Hàng dư"),
        ("delivered", "Đã nhận"),
    ], string="Tiến trình", default="not_applicable")

    def action_confirm_central_stock(self):
        for line in self:
            if line.fulfillment_method in ('internal', 'supplier_central') and line.internal_flow_state in ('pending_check', 'waiting_stock'):
                if line.central_on_hand_qty >= line.approved_qty:
                    line.internal_flow_state = 'ready_delivery'
                else:
                    line.internal_flow_state = 'waiting_stock'
        return True

    def action_confirm_central_stock_ready(self):
        for line in self:
            if line.internal_flow_state == 'ready_delivery' and not line.internal_picking_id:
                line.request_id._create_internal_pickings_for_lines(line)
        return True

    fulfillment_method = fields.Selection([
        ("internal", "Kho tổng có sẵn"),
        ("supplier_central", "NCC giao Kho tổng"),
        ("supplier", "NCC giao thẳng Cửa hàng"),
    ], string="Phương án đáp ứng")

    source_warehouse_id = fields.Many2one("stock.warehouse", string="Kho nguồn")
    supplier_id = fields.Many2one("res.partner", string="Nhà cung cấp")
    purchase_order_id = fields.Many2one("purchase.order", string="PO", readonly=True)
    internal_picking_id = fields.Many2one("stock.picking", string="Phiếu điều chuyển", readonly=True)
    store_receipt_picking_id = fields.Many2one("stock.picking", string="Phiếu nhận hàng", readonly=True)
    
    x_demand_status = fields.Selection([('normal', 'Bình thường'), ('high', 'Dư hàng'), ('low', 'Thiếu hàng'), ('stopped', 'Đã dừng đặt')], string="Tình trạng nhu cầu", compute="_compute_demand_status", store=True)
    central_on_hand_qty = fields.Float(string="Tồn Kho tổng", compute="_compute_supply_metrics")
    central_available_qty = fields.Float(string="Khả dụng Kho tổng", compute="_compute_supply_metrics")
    source_available_qty = fields.Float(string="Khả dụng Kho nguồn", compute="_compute_supply_metrics")
    availability_breakdown = fields.Char(string="Chi tiết tồn kho", compute="_compute_supply_metrics")
    store_on_hand_qty = fields.Float(string="Tồn Cửa hàng", compute="_compute_supply_metrics")
    central_stock_value = fields.Float(string="Giá trị tồn", compute="_compute_supply_metrics")
    remaining_after_dispatch_qty = fields.Float(string="Dự kiến còn sau giao", compute="_compute_supply_metrics")
    stock_ready_to_dispatch = fields.Boolean(string="Đủ hàng giao", compute="_compute_supply_metrics")
    route_status_display = fields.Char(string="Trạng thái xử lý", compute="_compute_route_status_display")

    @api.depends('product_id', 'product_id.x_mer_stop_ordering', 'store_on_hand_qty')
    def _compute_demand_status(self):
        for line in self:
            if line.product_id.x_mer_stop_ordering:
                line.x_demand_status = 'stopped'
                continue
            store = line.request_id.store_id
            if store:
                sl = self.env['store.product.line'].search([('store_id','=',store.id), ('product_id','=',line.product_id.id)], limit=1)
                if sl:
                    if line.store_on_hand_qty > sl.max_qty: line.x_demand_status = 'high'
                    elif line.store_on_hand_qty < sl.min_qty: line.x_demand_status = 'low'
                    else: line.x_demand_status = 'normal'
                else: line.x_demand_status = 'normal'
            else: line.x_demand_status = 'normal'

    def _compute_supply_metrics(self):
        for line in self:
            # Khởi tạo giá trị mặc định cho từng dòng
            central_on_hand = 0.0
            central_available = 0.0
            store_on_hand = 0.0
            source_available = 0.0
            breakdown = []
            
            # Chỉ thực hiện tính toán nếu product_id đã có ID thực (kiểu số nguyên)
            # Tránh lỗi khi Odoo tạo NewId cho các dòng nháp
            product_id = line.product_id.id
            if isinstance(product_id, int):
                try:
                    # 1. Tồn kho tổng: Vị trí chính của các kho 'central'
                    central_whs = self.env['stock.warehouse'].search([('mis_role','=','central')])
                    if central_whs:
                        target_location_ids = central_whs.mapped('lot_stock_id').ids
                        if target_location_ids:
                            self.env.cr.execute("""
                                SELECT SUM(quantity), SUM(quantity - reserved_quantity)
                                FROM stock_quant
                                WHERE product_id = %s AND location_id IN %s
                            """, (product_id, tuple(target_location_ids)))
                            res = self.env.cr.fetchone()
                            if res:
                                central_on_hand = res[0] if res[0] else 0.0
                                central_available = res[1] if res[1] else 0.0

                    # 2. Tồn cửa hàng: Vị trí kho chính (lot_stock_id) của cửa hàng
                    target_location = line.request_id.warehouse_id.lot_stock_id
                    if target_location:
                        self.env.cr.execute("""
                            SELECT SUM(quantity) FROM stock_quant 
                            WHERE product_id = %s AND location_id = %s
                        """, (product_id, target_location.id))
                        res_store = self.env.cr.fetchone()
                        store_on_hand = res_store[0] if res_store and res_store[0] else 0.0
                    
                    # 3. Khả dụng kho nguồn: Vị trí chính của kho nguồn
                    source_wh = line.source_warehouse_id or central_whs[:1]
                    if source_wh and source_wh.lot_stock_id:
                        self.env.cr.execute("""
                            SELECT SUM(quantity - reserved_quantity) FROM stock_quant 
                            WHERE product_id = %s AND location_id = %s
                        """, (product_id, source_wh.lot_stock_id.id))
                        res_source = self.env.cr.fetchone()
                        source_available = res_source[0] if res_source and res_source[0] else 0.0
                    
                    # 4. Chi tiết tồn kho
                    if central_whs:
                        for wh in central_whs:
                            if wh.lot_stock_id:
                                self.env.cr.execute("SELECT SUM(quantity) FROM stock_quant WHERE product_id = %s AND location_id = %s", (product_id, wh.lot_stock_id.id))
                                res_qty = self.env.cr.fetchone()
                                qty = res_qty[0] if res_qty and res_qty[0] else 0.0
                                if qty > 0:
                                    breakdown.append(f"{wh.name} ({wh.lot_stock_id.name}): {qty}")
                except Exception:
                    # Nếu có bất kỳ lỗi SQL nào, giữ nguyên giá trị 0
                    pass

            line.central_on_hand_qty = central_on_hand
            line.central_available_qty = central_available
            line.store_on_hand_qty = store_on_hand
            line.source_available_qty = source_available
            line.availability_breakdown = " | ".join(breakdown)
            
            # Giá trị tồn: Tồn kho tổng * Giá vốn (standard_price)
            line.central_stock_value = line.central_on_hand_qty * line.product_id.standard_price
            
            # Dự kiến còn sau giao
            line.remaining_after_dispatch_qty = line.source_available_qty - line.approved_qty
            line.stock_ready_to_dispatch = line.source_available_qty >= line.approved_qty

    @api.depends('fulfillment_method', 'internal_flow_state', 'purchase_order_id.state', 'internal_picking_id.state')
    def _compute_route_status_display(self):
        for line in self:
            if line.internal_flow_state == 'overstock': line.route_status_display = _("Hàng dư (Bị chặn)")
            elif line.fulfillment_method == 'supplier': line.route_status_display = _("Mua trực tiếp") if not line.purchase_order_id else _("Đã tạo PO")
            elif line.fulfillment_method == 'supplier_central': line.route_status_display = _("Mua về Kho tổng") if not line.purchase_order_id else _("Đang về Kho tổng")
            elif line.fulfillment_method == 'internal': line.route_status_display = dict(self._fields['internal_flow_state'].selection).get(line.internal_flow_state)
            else: line.route_status_display = _("Chưa xác định")

    def action_mer_stop_ordering(self):
        self.ensure_one()
        product = self.product_id
        product.sudo().write({'x_mer_stop_ordering': True})
        
        # Cập nhật tất cả các dòng cùng sản phẩm trong PR này về trạng thái dừng
        related_lines = self.request_id.line_ids.filtered(lambda l: l.product_id == product)
        related_lines.write({'approved_qty': 0, 'internal_flow_state': 'overstock'})
        
        # Kiểm tra xem còn dòng nào khác có thể đặt hàng không
        request = self.request_id
        # Một dòng được coi là "còn hoạt động" nếu sản phẩm chưa bị dừng đặt 
        # và có số lượng (số lượng duyệt > 0 hoặc số lượng yêu cầu > 0)
        active_lines = request.line_ids.filtered(lambda l: 
            not l.product_id.x_mer_stop_ordering and 
            (l.approved_qty > 0 or l.product_qty > 0)
        )
        
        if not active_lines and request.state in ['draft', 'submitted', 'to_approve', 'approved', 'po_created']:
            request.action_cancel()
            request.message_post(body=_("Yêu cầu đã tự động bị hủy do tất cả sản phẩm đều đã dừng đặt hàng."))
            
        return True

    def action_mer_reactivate_ordering(self):
        self.ensure_one()
        self.product_id.sudo().write({'x_mer_stop_ordering': False})
        return True

    def action_view_supply_stock(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Tồn kho: %s") % self.product_id.name,
            "res_model": "stock.quant",
            "view_mode": "list",
            "domain": [("product_id", "=", self.product_id.id), ("location_id.usage", "=", "internal")],
        }
