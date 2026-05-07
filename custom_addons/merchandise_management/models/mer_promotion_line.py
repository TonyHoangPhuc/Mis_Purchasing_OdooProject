import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class MerPromotionLine(models.Model):
    _name = 'mer.promotion.line'
    _description = 'Chi tiết khuyến mãi Merchandise'

    promotion_id = fields.Many2one('mer.promotion', string='Khuyến mãi', ondelete='cascade')
    promotion_id_state = fields.Selection(related='promotion_id.state', string='Trạng thái KM')
    warehouse_id = fields.Many2one('stock.warehouse', string='Cửa hàng', required=True)
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    discount_rate = fields.Float(string='Mức giảm (%)')
    qty_in_stores = fields.Float(string='Tồn tại Cửa hàng', compute='_compute_qty_in_stores')
    default_code = fields.Char(related='product_id.default_code', string='SKU')
    lst_price = fields.Float(related='product_id.lst_price', string='List Price')
    limit_qty = fields.Float(string='SL KM Tối đa', default=0.0, help='Giới hạn số lượng được bán với giá KM (Để 0 là không giới hạn)')
    
    sold_qty = fields.Float(string='Đã bán (Giao)', compute='_compute_sold_qty')
    reserved_qty = fields.Float(string='Đang đặt (Chưa giao)', compute='_compute_reserved_qty')
    remaining_qty = fields.Float(string='Còn lại', compute='_compute_remaining_qty')
    qty_available = fields.Float(string='Khả dụng', compute='_compute_qty_available')
    
    def _compute_qty_available(self):
        for line in self:
            # Tồn thực tế
            qty_in_stock = line.qty_in_stores
            # Trừ đi các KM khác
            other_promos = self.env['mer.promotion'].search([
                ('id', '!=', line.promotion_id.id)
            ])
            other_lines = other_promos.mapped('line_ids').filtered(
                lambda l: l.product_id == line.product_id and l.warehouse_id == line.warehouse_id
            )
            other_taken = 0.0
            for ol in other_lines:
                if ol.promotion_id.state == 'active':
                    other_taken += ol.remaining_qty + ol.reserved_qty
                else:
                    other_taken += ol.reserved_qty
            
            line.qty_available = max(0.0, qty_in_stock - other_taken)
    
    # Trường ẩn để lọc domain cửa hàng có hàng
    available_warehouse_ids = fields.Many2many('stock.warehouse', compute='_compute_available_warehouse_ids')
    
    @api.depends('product_id', 'promotion_id.target_store_ids')
    def _compute_available_warehouse_ids(self):
        for line in self:
            valid_wh_ids = []
            if line.product_id and line.promotion_id.target_store_ids:
                for wh in line.promotion_id.target_store_ids:
                    # Kiểm tra tồn kho thực tế
                    quants = self.env['stock.quant'].sudo().search([
                        ('product_id', '=', line.product_id.id),
                        ('location_id', 'child_of', wh.lot_stock_id.id),
                        ('quantity', '>', 0)
                    ])
                    if quants:
                        valid_wh_ids.append(wh.id)
            
            line.available_warehouse_ids = [(6, 0, valid_wh_ids)]

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Tự động tách dòng theo danh sách cửa hàng áp dụng (Chỉ lấy cửa hàng có tồn)."""
        if not self.product_id or not self.promotion_id.target_store_ids:
            return

        target_warehouses = self.promotion_id.target_store_ids
        valid_warehouses = []
        
        # Kiểm tra tồn kho tại từng cửa hàng
        for wh in target_warehouses:
            main_location = wh.lot_stock_id
            quants = self.env['stock.quant'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id', 'child_of', main_location.id),
                ('quantity', '>', 0),
            ])
            if sum(quants.mapped('quantity')) > 0:
                valid_warehouses.append(wh)

        # Nếu không cửa hàng nào có hàng, thông báo lỗi và xóa sản phẩm vừa chọn
        if not valid_warehouses:
            product_name = self.product_id.name
            self.product_id = False
            return {
                'warning': {
                    'title': _('Hết hàng tồn kho'),
                    'message': _('Sản phẩm "%s" hiện không còn tồn kho tại (các) cửa hàng bạn đã chọn ở trên. Vui lòng kiểm tra lại.') % product_name
                }
            }

        # Lọc danh sách warehouse có tồn kho để trả về domain cho UI
        domain = {'warehouse_id': [('id', 'in', [wh.id for wh in valid_warehouses])]}

        # 1. Nếu dòng này chưa có cửa hàng, hoặc cửa hàng hiện tại KHÔNG có tồn cho SP này
        # thì tự động gán cửa hàng đầu tiên có tồn.
        if not self.warehouse_id or self.warehouse_id.id not in [wh.id for wh in valid_warehouses]:
            self.warehouse_id = valid_warehouses[0]
            self._compute_qty_in_stores()

            # 2. Chỉ tự động tách thêm các dòng mới nếu đây là dòng mới tạo (chưa có trong DB)
            if len(valid_warehouses) > 1 and not self._origin:
                for wh in valid_warehouses[1:]:
                    self.promotion_id.line_ids = [(0, 0, {
                        'product_id': self.product_id.id,
                        'warehouse_id': wh.id,
                        'discount_rate': 0.0,
                        'limit_qty': 0.0,
                    })]
        
        return {'domain': domain}

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        self._compute_qty_in_stores()

    @api.onchange('limit_qty', 'product_id', 'warehouse_id')
    def _onchange_limit_qty_check(self):
        if self.limit_qty <= 0 or not self.product_id or not self.warehouse_id:
            return
        
        # Tương tự logic check constraint nhưng dùng cho cảnh báo nhanh
        other_active_promos = self.env['mer.promotion'].search([
            ('state', '=', 'active'),
            ('id', '!=', self.promotion_id._origin.id if self.promotion_id else False)
        ])
        other_active_lines = other_active_promos.mapped('line_ids').filtered(
            lambda l: l.product_id == self.product_id and l.warehouse_id == self.warehouse_id
        )
        other_reserved = sum(other_active_lines.mapped(lambda l: l.remaining_qty + l.reserved_qty))
        available_qty = self.qty_in_stores - other_reserved

        if self.limit_qty > available_qty:
            return {
                'warning': {
                    'title': _("Cảnh báo số lượng"),
                    'message': _(
                        'Số lượng bạn nhập (%s) vượt quá số lượng khả dụng (%s) tại cửa hàng này. '
                        'Bạn vẫn có thể lưu ở trạng thái Nháp, nhưng hệ thống sẽ chặn khi bạn kích hoạt hoặc lưu chính thức.'
                    ) % (self.limit_qty, max(0.0, available_qty))
                }
            }

    @api.depends('product_id', 'warehouse_id')
    def _compute_sold_qty(self):
        for line in self:
            line.sold_qty = 0.0
            if line.product_id and line.warehouse_id:
                # Tìm các Sale Order Line có gắn dòng KM này
                lines = self.env['sale.order.line'].sudo().search([
                    ('promotion_line_id', '=', line._origin.id if hasattr(line, '_origin') else line.id),
                    ('state', 'in', ['sale', 'done'])
                ])
                
                # 1. Đã bán: Chỉ tính khi hàng THỰC SỰ RỜI KHO CỬA HÀNG (Internal -> Customer)
                done_moves = lines.mapped('move_ids').filtered(
                    lambda m: m.state == 'done' and 
                              m.location_id.usage == 'internal' and
                              m.location_dest_id.usage == 'customer'
                )
                line.sold_qty = sum(done_moves.mapped('quantity'))
                
                if not lines.mapped('move_ids'):
                    line.sold_qty = sum(lines.mapped('qty_delivered'))

    @api.depends('product_id', 'warehouse_id', 'promotion_id.state')
    def _compute_reserved_qty(self):
        for line in self:
            line.reserved_qty = 0.0
            real_id = line._origin.id if hasattr(line, '_origin') and line._origin.id else (line.id if line.id and not isinstance(line.id, models.NewId) else False)
            if real_id:
                lines = self.env['sale.order.line'].sudo().search([
                    ('promotion_line_id', '=', real_id),
                    ('state', 'in', ['sale', 'done'])
                ])
                total_delivered = sum(lines.mapped('move_ids').filtered(lambda m: m.state == 'done').mapped('quantity'))
                total_ordered = sum(lines.mapped('product_uom_qty'))
                line.reserved_qty = max(0.0, total_ordered - total_delivered)

    @api.depends('limit_qty', 'sold_qty', 'reserved_qty', 'qty_available')
    def _compute_remaining_qty(self):
        for line in self:
            # Suất còn lại theo hạn mức đã đặt
            remaining_by_limit = 0.0
            if line.limit_qty > 0:
                remaining_by_limit = max(0.0, line.limit_qty - line.sold_qty - line.reserved_qty)
            
            # Tuy nhiên không được vượt quá số lượng thực tế còn lại trong kho (sau khi trừ các KM khác)
            # Điều này giúp cột "Còn lại" tự cập nhật khi có KM khác chiếm hàng
            if line.promotion_id.state == 'draft':
                line.remaining_qty = min(remaining_by_limit, line.qty_available)
            else:
                line.remaining_qty = remaining_by_limit

    def _compute_qty_in_stores(self):
        for line in self:
            if not line.warehouse_id or not line.product_id:
                line.qty_in_stores = 0.0
                continue

            # Chỉ tính tồn kho tại các địa điểm lưu trữ chính (lot_stock_id) của Cửa hàng này
            main_location = line.warehouse_id.lot_stock_id
            quants = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', 'child_of', main_location.id),
                ('quantity', '>', 0),
            ])
            line.qty_in_stores = sum(quants.mapped('quantity'))

    @api.constrains('promotion_id', 'product_id', 'warehouse_id', 'limit_qty')
    def _check_limit_qty_availability(self):
        from odoo.tools import float_compare
        for line in self:
            if line.limit_qty <= 0 or not line.product_id or not line.warehouse_id:
                continue
            
            # 1. Tồn kho thực tế tại cửa hàng
            qty_in_stock = line.qty_in_stores
            
            # 2. Số lượng đã bị chiếm bởi các KM khác:
            # - Trừ "Còn lại" của các KM đang chạy (Active)
            # - Trừ "Đang đặt" của TẤT CẢ KM (kể cả đã kết thúc nhưng hàng chưa đi)
            other_promos = self.env['mer.promotion'].search([
                ('id', '!=', line.promotion_id.id)
            ])
            other_lines = other_promos.mapped('line_ids').filtered(
                lambda l: l.product_id == line.product_id and l.warehouse_id == line.warehouse_id
            )
            other_reserved = 0.0
            for ol in other_lines:
                if ol.promotion_id.state == 'active':
                    other_reserved += ol.remaining_qty + ol.reserved_qty
                else:
                    other_reserved += ol.reserved_qty
            
            available_qty = qty_in_stock - other_reserved
            
            if float_compare(line.limit_qty, available_qty, precision_digits=2) > 0:
                raise ValidationError(_(
                    'Sản phẩm "%s" tại cửa hàng "%s" chỉ còn tối đa %s suất khả dụng '
                    '(do đã trừ %s suất đang chạy ở các chương trình khác). '
                    'Bạn không thể nhập số lượng %s.'
                ) % (line.product_id.name, line.warehouse_id.name, max(0.0, available_qty), other_reserved, line.limit_qty))

    @api.constrains('promotion_id', 'product_id', 'warehouse_id')
    def _check_duplicate_product_warehouse(self):
        for line in self:
            if not line.promotion_id or not line.product_id or not line.warehouse_id:
                continue
            
            # Tìm các dòng khác trong cùng 1 KM có cùng SP và Kho
            duplicate = self.env['mer.promotion.line'].search([
                ('promotion_id', '=', line.promotion_id.id),
                ('product_id', '=', line.product_id.id),
                ('warehouse_id', '=', line.warehouse_id.id),
                ('id', '!=', line.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    'Sản phẩm "%s" tại cửa hàng "%s" đã tồn tại trong danh sách. '
                    'Vui lòng không nhập trùng lặp.'
                ) % (line.product_id.display_name, line.warehouse_id.name))
