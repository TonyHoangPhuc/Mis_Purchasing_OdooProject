import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class MerPromotionLine(models.Model):
    _name = 'mer.promotion.line'
    _description = 'Chi tiết khuyến mãi Merchandise'

    promotion_id = fields.Many2one('mer.promotion', string='Khuyến mãi', ondelete='cascade')
    warehouse_id = fields.Many2one('stock.warehouse', string='Cửa hàng', required=True)
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    discount_rate = fields.Float(string='Mức giảm (%)')
    qty_in_stores = fields.Float(string='Tồn tại Cửa hàng', compute='_compute_qty_in_stores')
    default_code = fields.Char(related='product_id.default_code', string='SKU')
    lst_price = fields.Float(related='product_id.lst_price', string='List Price')
    limit_qty = fields.Float(string='SL KM Tối đa', default=0.0, help='Giới hạn số lượng được bán với giá KM (Để 0 là không giới hạn)')
    
    sold_qty = fields.Float(string='Đã bán (Giao)', compute='_compute_sold_qty', store=True)
    reserved_qty = fields.Float(string='Đang đặt (Chưa giao)', compute='_compute_reserved_qty')
    remaining_qty = fields.Float(string='Còn lại', compute='_compute_remaining_qty')

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

        # CHỈ TỰ ĐỘNG TÁCH DÒNG NẾU DÒNG NÀY CHƯA CÓ CỬA HÀNG (Tránh vòng lặp)
        if self.warehouse_id and self.warehouse_id.id in [wh.id for wh in valid_warehouses]:
            return

        # 1. Gán cửa hàng có tồn đầu tiên cho dòng hiện tại
        self.warehouse_id = valid_warehouses[0]

        # 2. Nếu có nhiều cửa hàng có tồn, tạo thêm các dòng mới cho các cửa hàng còn lại
        if len(valid_warehouses) > 1:
            for wh in valid_warehouses[1:]:
                # Sử dụng gán trực tiếp với Command.create để tạo dòng cho các kho còn lại
                self.promotion_id.line_ids = [(0, 0, {
                    'product_id': self.product_id.id,
                    'warehouse_id': wh.id,
                    'discount_rate': 0.0,
                    'limit_qty': 0.0,
                })]

    @api.depends('product_id')
    def _compute_sold_qty(self):
        for line in self:
            line.sold_qty = 0.0
            if line.product_id and line.promotion_id:
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

    @api.depends('product_id')
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

    @api.depends('limit_qty', 'sold_qty', 'reserved_qty')
    def _compute_remaining_qty(self):
        for line in self:
            if line.limit_qty > 0:
                line.remaining_qty = max(0.0, line.limit_qty - line.sold_qty - line.reserved_qty)
            else:
                line.remaining_qty = 0.0

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
