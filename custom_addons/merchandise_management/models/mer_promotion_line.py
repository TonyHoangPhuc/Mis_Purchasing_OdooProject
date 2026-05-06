from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MerPromotionLine(models.Model):
    _name = 'mer.promotion.line'
    _description = 'Promotion Line'

    promotion_id = fields.Many2one('mer.promotion', string='Promotion', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    discount_rate = fields.Float(string='Discount (%)')
    qty_in_stores = fields.Float(string='Store Qty', compute='_compute_qty_in_stores')
    default_code = fields.Char(related='product_id.default_code', string='SKU')
    lst_price = fields.Float(related='product_id.lst_price', string='List Price')
    limit_qty = fields.Float(string='SL KM Tối đa', default=0.0, help='Giới hạn số lượng được bán với giá KM (Để 0 là không giới hạn)')
    sold_qty = fields.Float(string='Đã bán', compute='_compute_sold_qty', copy=False)
    reserved_qty = fields.Float(string='Giữ chỗ', compute='_compute_reserved_qty')
    remaining_qty = fields.Float(string='Còn lại', compute='_compute_remaining_qty')

    @api.depends('product_id')
    def _compute_sold_qty(self):
        for line in self:
            line.sold_qty = 0.0
            real_id = line._origin.id if hasattr(line, '_origin') and line._origin.id else (line.id if line.id and not isinstance(line.id, models.NewId) else False)
            if real_id:
                lines = self.env['sale.order.line'].sudo().search([
                    ('promotion_line_id', '=', real_id),
                    ('state', 'in', ['sale', 'done'])
                ])
                
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error("!!! COMPUTE SOLD QTY FOR KM %s | SO Lines: %s", real_id, lines.ids)
                
                # 1. Đã bán: Chỉ tính khi hàng THỰC SỰ RỜI KHO CỬA HÀNG (Internal -> Customer)
                done_moves = lines.mapped('move_ids').filtered(
                    lambda m: m.state == 'done' and 
                              m.location_id.usage == 'internal' and
                              m.location_dest_id.usage == 'customer'
                )
                
                for m in done_moves:
                    _logger.error("   -> FOUND DONE MOVE: %s | SO: %s | Qty: %s", m.id, m.sale_line_id.order_id.name, m.quantity)
                
                line.sold_qty = sum(done_moves.mapped('quantity'))
                
                # Nếu không có move (ví dụ sản phẩm dịch vụ), dùng qty_delivered trực tiếp từ SO Line
                if not lines.mapped('move_ids'):
                    _logger.error("   -> NO MOVES FOUND, USING QTY_DELIVERED")
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

    @api.depends('limit_qty', 'sold_qty')
    def _compute_remaining_qty(self):
        for line in self:
            if line.limit_qty > 0:
                line.remaining_qty = max(0.0, line.limit_qty - line.sold_qty)
                if line.remaining_qty <= 0:
                    line.env['mer.promotion']._update_product_prices(products=line.product_id)
                    if line.promotion_id.state == 'active' and line.promotion_id._all_limited_lines_exhausted():
                        line.promotion_id.action_expire()
            else:
                line.remaining_qty = 0.0

    @api.depends('product_id', 'promotion_id.target_store_ids')
    def _compute_qty_in_stores(self):
        for line in self:
            warehouses = line.promotion_id.target_store_ids
            if not warehouses:
                line.qty_in_stores = 0.0
                continue

            # Chỉ tính tồn kho tại các địa điểm lưu trữ chính (lot_stock_id) và con của nó
            # Loại trừ các địa điểm như Hàng nhận dư nếu chúng nằm ngoài cây địa điểm chính
            main_locations = warehouses.mapped('lot_stock_id')
            quants = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', 'child_of', main_locations.ids),
                ('quantity', '>', 0),
            ])
            line.qty_in_stores = sum(quants.mapped('quantity'))
