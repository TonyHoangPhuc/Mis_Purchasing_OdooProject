from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MerDiscrepancyReport(models.Model):
    _name = 'mer.discrepancy.report'
    _description = 'Báo cáo sai lệch hàng hóa'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã báo cáo', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    
    state = fields.Selection([
        ('draft', 'Mới'),
        ('reporting', 'Đang báo cáo'),
        ('solving', 'Đang giải quyết'),
        ('done', 'Hoàn tất'),
        ('cancel', 'Hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    date_discrepancy = fields.Date(string='Ngày ghi nhận', default=fields.Date.today)
    
    user_id = fields.Many2one('res.users', string='Người báo cáo', default=lambda self: self.env.user)
    
    picking_id = fields.Many2one('stock.picking', string='Phiếu kho liên quan')
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('mer.discrepancy.report') or _('New')
        return super(MerDiscrepancyReport, self).create(vals_list)

    @api.depends('expected_qty', 'actual_qty')
    def _compute_difference(self):
        for record in self:
            record.difference_qty = record.actual_qty - record.expected_qty

    def action_confirm_report(self):
        self.write({'state': 'reporting'})

    def action_start_solving(self):
        self.write({'state': 'solving'})
        
    def action_done(self):
        for report in self:
            report.message_post(
                body=_("Báo cáo sai lệch được hoàn tất thủ công."),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        self.write({'state': 'done'})

    def action_create_replenishment_po(self):
        self.ensure_one()
        if self.reason != 'shortage':
            raise UserError(_("Chỉ có thể tạo PO bù hàng cho trường hợp Hàng thiếu."))
        
        if self.replenishment_po_id:
            raise UserError(_("Báo cáo này đã tạo PO bù hàng trước đó."))

        # Xác định nơi nhận đơn bù thiếu (Kho tổng hay Nhà cung cấp)
        partner_id = False
        if self.product_id.x_mer_supply_route == 'warehouse':
            partner_id = self.env.company.partner_id.id
        else:
            if self.purchase_id and self.purchase_id.partner_id:
                partner_id = self.purchase_id.partner_id.id
            else:
                seller = self.product_id.seller_ids[:1]
                if seller:
                    partner_id = seller.partner_id.id

        if not partner_id:
            raise UserError(_("Không xác định được nơi nhận đơn bù thiếu (Kho tổng hoặc Nhà cung cấp). Vui lòng kiểm tra lại cấu hình Luồng cung ứng trên sản phẩm."))

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
        
        po = self.env['purchase.order'].create(purchase_vals)
        self.write({
            'replenishment_po_id': po.id,
            'state': 'done',
            'solution_notes': f"Đã tự động xử lý Hàng thiếu: Sinh Đơn mua hàng (PO) bù số lượng: {po.name}"
        })
        
        self.message_post(body=_("Đã tự động tạo PO bù hàng và Hoàn tất báo cáo: <a href='#' data-oe-model='purchase.order' data-oe-id='%s'>%s</a>") % (po.id, po.name))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_return_picking(self):
        self.ensure_one()
        if self.reason != 'overage':
            raise UserError(_("Chỉ có thể tạo Phiếu thu hồi cho trường hợp Hàng dư."))
            
        if self.return_picking_id:
            raise UserError(_("Báo cáo này đã tạo Phiếu thu hồi trước đó."))

        # Xác định Partner, Picking Type và Locations
        partner_id = False
        picking_type = False
        location_source_id = False
        location_dest_id = False
        
        # 1. Ưu tiên lấy thông tin từ phiếu gốc nếu có
        if self.picking_id:
            location_source_id = self.picking_id.location_dest_id.id
            location_dest_id = self.picking_id.location_id.id
            
            # Lấy đích danh Đối tác (Partner) là Kho tổng hoặc Nhà cung cấp đã gửi từ phiếu gốc
            if self.picking_id.partner_id:
                partner_id = self.picking_id.partner_id.id
            
            if self.picking_id.picking_type_id.return_picking_type_id:
                picking_type = self.picking_id.picking_type_id.return_picking_type_id
            else:
                picking_type = self.picking_id.picking_type_id
                
        # Thử tìm Warehouse từ phiếu gốc
        warehouse = self.picking_id.picking_type_id.warehouse_id if self.picking_id else False

        if self.product_id.x_mer_supply_route == 'warehouse':
            if not partner_id:
                partner_id = self.env.company.partner_id.id
            if not picking_type:
                domain = [('code', '=', 'internal')]
                if warehouse:
                    picking_type = self.env['stock.picking.type'].search(domain + [('warehouse_id', '=', warehouse.id)], limit=1)
                
                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search(domain + ['|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)], limit=1)
                
                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search(domain, limit=1)
                
            if not location_dest_id:
                location_dest_id = picking_type.default_location_dest_id.id if picking_type else False
        else:
            if not partner_id:
                if self.purchase_id and self.purchase_id.partner_id:
                    partner_id = self.purchase_id.partner_id.id
                else:
                    seller = self.product_id.seller_ids[:1]
                    partner_id = seller.partner_id.id if seller else False
            
            if not picking_type:
                domain = [('code', '=', 'outgoing')]
                if warehouse:
                    picking_type = self.env['stock.picking.type'].search(domain + [('warehouse_id', '=', warehouse.id)], limit=1)

                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search(domain + ['|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)], limit=1)
                
                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search(domain, limit=1)
                    
                # Bổ sung: fallback nếu không có outgoing picking type (VD: hệ thống không cài app Bán Hàng)
                if not picking_type:
                    domain = [('code', '=', 'incoming')]
                    picking_type = self.env['stock.picking.type'].search(domain + ['|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)], limit=1)
                    if not picking_type:
                        picking_type = self.env['stock.picking.type'].search(domain, limit=1)
                
            if not location_dest_id:
                location_dest_id = self.env.ref('stock.stock_location_suppliers').id

        if not partner_id:
            raise UserError(_("Không xác định được nơi nhận hàng (Kho tổng hoặc Nhà cung cấp)."))
            
        if not picking_type:
            raise UserError(_("Không tìm thấy Loại Hình Giao Nhận (Picking Type) phù hợp cho việc trả hàng trong hệ thống kho. Vui lòng kiểm tra lại cấu hình Kho."))

        qty_to_return = abs(self.difference_qty)
        if qty_to_return <= 0:
            raise UserError(_("Số lượng cần thu hồi phải lớn hơn 0."))

        if not location_source_id:
            location_source_id = picking_type.default_location_src_id.id
            if not location_source_id:
                # Nếu không xác định được location_source_id, thử lấy location từ warehouse
                wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
                location_source_id = wh.lot_stock_id.id if wh else False

        picking_vals = {
            'partner_id': partner_id,
            'picking_type_id': picking_type.id,
            'location_id': location_source_id,
            'location_dest_id': location_dest_id,
            'origin': f"Thu hồi dư - Báo cáo {self.name}",
            'move_ids': [(0, 0, {
                'name': self.product_id.name,
                'product_id': self.product_id.id,
                'product_uom_qty': qty_to_return,
                'product_uom': self.product_id.uom_id.id,
                'location_id': location_source_id,
                'location_dest_id': location_dest_id,
            })]
        }
        
        new_picking = self.env['stock.picking'].create(picking_vals)
        new_picking.action_confirm() # Xác nhận để vào trạng thái Chờ xử lý

        self.write({
            'return_picking_id': new_picking.id,
            'state': 'done',
            'solution_notes': f"Đã tự động tạo Phiếu kho yêu cầu thu hồi hàng dư: {new_picking.name}"
        })
        
        self.message_post(body=_("Đã tự động tạo Yêu cầu thu hồi, hoàn tất báo cáo: <a href='#' data-oe-model='stock.picking' data-oe-id='%s'>%s</a>") % (new_picking.id, new_picking.name))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': new_picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

