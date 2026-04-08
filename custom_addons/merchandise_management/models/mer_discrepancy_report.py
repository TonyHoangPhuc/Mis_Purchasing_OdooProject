from odoo import models, fields, api, _
from odoo.exceptions import UserError

# Quản lý sai lệch giữa hàng thực tế và chứng từ PO
class MerDiscrepancyReport(models.Model):
    _name = 'mer.discrepancy.report'
    _description = 'Báo cáo sai lệch hàng hóa'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã báo cáo', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    
    state = fields.Selection([
        ('draft', 'Mới'),
        ('done', 'Hoàn tất'),
        ('cancel', 'Hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    date_discrepancy = fields.Date(string='Ngày ghi nhận', default=fields.Date.today)
    
    user_id = fields.Many2one('res.users', string='Người báo cáo', default=lambda self: self.env.user)
    
    purchase_id = fields.Many2one('purchase.order', string='Đơn mua hàng liên quan')
    replenishment_po_id = fields.Many2one('purchase.order', string='PO bù hàng', readonly=True, tracking=True)
    return_picking_id = fields.Many2one('stock.picking', string='Phiếu thu hồi', readonly=True, tracking=True)
    
    product_id = fields.Many2one('product.product', string='Sản phẩm sai lệch', required=True)
    expected_qty = fields.Float(string='Số lượng theo chứng từ')
    actual_qty = fields.Float(string='Số lượng nhận thực tế')
    difference_qty = fields.Float(string='Chênh lệch', compute='_compute_difference', store=True)
    
    reason = fields.Selection([
        ('overage', 'Hàng dư'),
        ('shortage', 'Hàng thiếu')
    ], string='Lý do', required=True)
    
    solution_notes = fields.Text(string='Phương án giải quyết')
    
    warehouse_partner_id = fields.Many2one('res.partner', string='Bộ phận Kho tiếp nhận')

    # Sinh mã báo cáo theo sequence khi tạo mới
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('mer.discrepancy.report') or _('New')
        return super(MerDiscrepancyReport, self).create(vals_list)

    warehouse_id = fields.Many2one('stock.warehouse', string='Cửa hàng', required=True, default=lambda self: self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1))

    # Cập nhật Cửa hàng dựa trên PO được chọn
    @api.onchange('purchase_id')
    def _onchange_purchase_id(self):
        if self.purchase_id and self.purchase_id.picking_type_id.warehouse_id:
            self.warehouse_id = self.purchase_id.picking_type_id.warehouse_id.id

    # Gợi ý lý do dư/thiếu dựa trên số lượng thực tế
    @api.onchange('expected_qty', 'actual_qty')
    def _onchange_qty_reason(self):
        if self.actual_qty > self.expected_qty:
            self.reason = 'overage'
        elif self.actual_qty < self.expected_qty:
            self.reason = 'shortage'
        else:
            self.reason = False

    # Tính số lượng chênh lệch thực tế vs chứng từ
    @api.depends('expected_qty', 'actual_qty')
    def _compute_difference(self):
        for record in self:
            record.difference_qty = record.actual_qty - record.expected_qty

    # Xác nhận hoàn tất báo cáo thủ công
    def action_done(self):
        for report in self:
            report.message_post(
                body=_("Báo cáo sai lệch được hoàn tất thủ công."),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        self.write({'state': 'done'})

    # Kiểm tra tính đúng đắn giữa số lượng và lý do
    @api.constrains('expected_qty', 'actual_qty', 'reason')
    def _check_qty_reason_consistency(self):
        for record in self:
            if record.actual_qty > record.expected_qty and record.reason == 'shortage':
                raise UserError(_("Logic sai lệch không khớp: Số lượng thực tế lớn hơn chứng từ thì lý do phải là Hàng dư."))
            if record.actual_qty < record.expected_qty and record.reason == 'overage':
                raise UserError(_("Logic sai lệch không khớp: Số lượng thực tế nhỏ hơn chứng từ thì lý do phải là Hàng thiếu."))

    # Tạo PO bù hàng thiếu
    def action_create_replenishment_po(self):
        self.ensure_one()
        # Kiểm tra logic lại một lần nữa trước khi tạo
        if self.actual_qty > self.expected_qty:
            self.reason = 'overage'
        elif self.actual_qty < self.expected_qty:
            self.reason = 'shortage'
            
        if self.state != 'draft':
            raise UserError(_("Bạn chỉ có thể tạo PO bù hàng khi báo cáo đang ở trạng thái Nháp."))
        
        if not self.purchase_id:
            raise UserError(_("Vui lòng chọn Đơn mua hàng liên quan (Source PO) trước khi tạo PO bù hàng."))

        if self.reason != 'shortage':
            raise UserError(_("Lý do hiện tại là %s. Chỉ có thể tạo PO bù hàng cho trường hợp Hàng thiếu.") % dict(self._fields['reason'].selection).get(self.reason))
        
        if self.replenishment_po_id:
            raise UserError(_("Báo cáo này đã tạo PO bù hàng trước đó."))

        # Xác định đối tác nhận đơn (Kho tổng hoặc NCC)
        partner_id = self.purchase_id.partner_id.id

        qty_to_order = abs(self.difference_qty)
        if qty_to_order <= 0:
            raise UserError(_("Số lượng cần bù phải lớn hơn 0."))

        purchase_vals = {
            'partner_id': partner_id,
            'origin': f"Bù thiếu - Báo cáo: {self.name}",
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': self.product_id.id,
                'name': self.product_id.name,
                'product_qty': qty_to_order,
                'product_uom_id': self.product_id.uom_id.id,
                'price_unit': self.product_id.standard_price,
                'date_planned': fields.Datetime.now(),
            })]
        }
        
        po = self.env['purchase.order'].sudo().create(purchase_vals)
        self.write({
            'replenishment_po_id': po.id,
            'state': 'done',
            'solution_notes': f"Đã tự động xử lý Hàng thiếu: Sinh Đơn mua hàng (PO) bù số lượng: {po.name}"
        })
        
        # Gửi thông báo Chatter cho Kho/NCC
        if partner_id:
            from markupsafe import Markup
            
            message_body = Markup(
                "<div style='background-color: #eff6ff; border-left: 5px solid #3b82f6; padding: 15px; border-radius: 4px; font-family: sans-serif;'>"
                    "<h3 style='margin-top: 0; color: #1e40af; border-bottom: 1px solid #bfdbfe; padding-bottom: 8px;'>🛒 %s</h3>"
                    "<p style='color: #1e3a8a; margin: 10px 0;'>"
                        "Chào bộ phận Kho, hệ thống ghi nhận một yêu cầu <b>Bù hàng thiếu</b> từ Merchandise:"
                    "</p>"
                    "<ul style='list-style: none; padding: 0; margin: 10px 0; color: #1e3a8a; line-height: 1.6;'>"
                        "<li><b>🔢 %s:</b> %s</li>"
                        "<li><b>📦 %s:</b> %s</li>"
                        "<li><b>➕ %s:</b> <span style='font-size: 1.1em; color: #2563eb;'>%s</span></li>"
                    "</ul>"
                    "<p style='margin-bottom: 0; font-style: italic; color: #1e40af; font-size: 0.9em; border-top: 1px dashed #bfdbfe; padding-top: 8px;'>"
                        "💡 <i>Vui lòng chuẩn bị hàng và giao bù cho Cửa hàng sớm nhất!</i>"
                    "</p>"
                "</div>"
            ) % (
                _("THÔNG BÁO BÙ HÀNG THIẾU (PO BÙ)"),
                _("Mã PO bù"), po.name,
                _("Sản phẩm"), self.product_id.display_name,
                _("Số lượng bù"), qty_to_order,
            )
            
        # Đăng ký theo dõi và gửi tin nhắn
            self.message_subscribe(partner_ids=[partner_id])
            self.message_post(
                body=message_body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                partner_ids=[partner_id]
            )
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # Tạo phiếu thu hồi hàng dư
    def action_create_return_picking(self):
        self.ensure_one()
        # Kiểm tra logic lại một lần nữa trước khi tạo
        if self.actual_qty > self.expected_qty:
            self.reason = 'overage'
        elif self.actual_qty < self.expected_qty:
            self.reason = 'shortage'

        if self.state != 'draft':
            raise UserError(_("Bạn chỉ có thể tạo Phiếu thu hồi khi báo cáo đang ở trạng thái Nháp."))
        
        if not self.purchase_id:
            raise UserError(_("Vui lòng chọn Đơn mua hàng liên quan (Source PO) trước khi tạo phiếu thu hồi."))

        if self.reason != 'overage':
            raise UserError(_("Lý do hiện tại là %s. Chỉ có thể tạo Phiếu thu hồi cho trường hợp Hàng dư.") % dict(self._fields['reason'].selection).get(self.reason))
            
        if self.return_picking_id:
            raise UserError(_("Báo cáo này đã tạo Phiếu thu hồi trước đó."))

        # Xác định đối tác liên quan
        partner_id = self.purchase_id.partner_id.id if self.purchase_id else False

        # Lấy thông tin Kho/Cửa hàng
        warehouse = self.warehouse_id

        if self.product_id.x_mer_supply_route == 'warehouse':
            # Trả Kho tổng: Dùng phiếu điều chuyển nội bộ
            picking_type = warehouse.int_type_id
            location_source_id = picking_type.default_location_src_id.id if picking_type else warehouse.lot_stock_id.id
            location_dest_id = picking_type.default_location_dest_id.id if picking_type else self.env.company.partner_id.property_stock_customer.id
        else:
            # Trả NCC: Dùng phiếu xuất hàng
            picking_type = warehouse.out_type_id
            
            # Dự phòng nếu thiếu cấu hình loại hình xuất
            if not picking_type:
                picking_type = self.env['stock.picking.type'].sudo().search([
                    ('code', '=', 'outgoing'),
                    ('warehouse_id', '=', warehouse.id)
                ], limit=1)

            location_source_id = warehouse.lot_stock_id.id
            location_dest_id = self.env.ref('stock.stock_location_suppliers', raise_if_not_found=False)
            location_dest_id = location_dest_id.id if location_dest_id else (picking_type.default_location_dest_id.id if picking_type else False)

        if not picking_type:
            # Nếu vẫn không thấy, lấy bất kỳ loại hình nào có code là outgoing/internal trong công ty
            picking_type = self.env['stock.picking.type'].sudo().search([
                ('code', 'in', ['outgoing', 'internal']),
                ('company_id', '=', self.env.company.id)
            ], limit=1)

        if not picking_type:
            raise UserError(_("Hệ thống không tìm thấy Loại hình giao nhận nào để tạo phiếu. Vui lòng kiểm tra lại cấu hình kho của Cửa hàng này."))

        qty_to_return = abs(self.difference_qty)
        if qty_to_return <= 0:
            raise UserError(_("Số lượng cần thu hồi phải lớn hơn 0."))

        if not location_source_id:
            location_source_id = picking_type.default_location_src_id.id
            if not location_source_id:
            # Dự phòng lấy kho mặc định của công ty
                wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
                location_source_id = wh.lot_stock_id.id if wh else False

        picking_vals = {
            'partner_id': partner_id,
            'picking_type_id': picking_type.id,
            'location_id': location_source_id,
            'location_dest_id': location_dest_id,
            'origin': f"Thu hồi dư - Báo cáo {self.name}",
            'move_ids': [(0, 0, {
                'description_picking': self.product_id.name,
                'product_id': self.product_id.id,
                'product_uom_qty': qty_to_return,
                'product_uom': self.product_id.uom_id.id,
                'location_id': location_source_id,
                'location_dest_id': location_dest_id,
            })]
        }
        
        new_picking = self.env['stock.picking'].sudo().create(picking_vals)
        new_picking.sudo().action_confirm() # Xác nhận phiếu kho

        self.write({
            'return_picking_id': new_picking.id,
            'state': 'done',
            'solution_notes': f"Đã tự động tạo Phiếu kho yêu cầu thu hồi hàng dư: {new_picking.name}"
        })
        
        # Gửi thông báo Chatter cho Kho/NCC
        if partner_id:
            from markupsafe import Markup
            
            message_body = Markup(
                "<div style='background-color: #fffbef; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 4px; font-family: sans-serif;'>"
                    "<h3 style='margin-top: 0; color: #92400e; border-bottom: 1px solid #fef3c7; padding-bottom: 8px;'>⚠️ %s</h3>"
                    "<p style='color: #78350f; margin: 10px 0;'>"
                        "Chào bộ phận Kho, hệ thống ghi nhận một yêu cầu <b>Thu hồi hàng dư</b> từ Merchandise:"
                    "</p>"
                    "<ul style='list-style: none; padding: 0; margin: 10px 0; color: #78350f; line-height: 1.6;'>"
                        "<li><b>🚚 %s:</b> %s</li>"
                        "<li><b>📦 %s:</b> %s</li>"
                        "<li><b>➖ %s:</b> <span style='font-size: 1.1em; color: #d97706;'>%s</span></li>"
                    "</ul>"
                    "<p style='margin-bottom: 0; font-style: italic; color: #92400e; font-size: 0.9em; border-top: 1px dashed #fef3c7; padding-top: 8px;'>"
                        "💡 <i>Vui lòng lên lịch thu hồi và đến Cửa hàng để mang hàng dư về!</i>"
                    "</p>"
                "</div>"
            ) % (
                _("THÔNG BÁO THU HỒI HÀNG DƯ"),
                _("Mã Phiếu kho"), new_picking.name,
                _("Sản phẩm"), self.product_id.display_name,
                _("Số lượng thu hồi"), qty_to_return,
            )
            
            # Thêm Kho vào danh sách theo dõi và bắn tin nhắn
            self.message_subscribe(partner_ids=[partner_id])
            self.message_post(
                body=message_body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                partner_ids=[partner_id]
            )
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': new_picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

