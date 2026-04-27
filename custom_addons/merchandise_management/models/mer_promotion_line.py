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
    sold_qty = fields.Float(string='Đã bán', default=0.0, copy=False)
    remaining_qty = fields.Float(string='Còn lại', compute='_compute_remaining_qty')

    @api.depends('limit_qty', 'sold_qty')
    def _compute_remaining_qty(self):
        for line in self:
            if line.limit_qty > 0:
                line.remaining_qty = max(0.0, line.limit_qty - line.sold_qty)
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

    @api.constrains('limit_qty')
    def _check_limit_qty(self):
        for line in self:
            if line.limit_qty > 0 and round(line.limit_qty, 2) > round(line.qty_in_stores, 2):
                raise ValidationError(_("Số lượng KM tối đa (%s) của sản phẩm '%s' không được lớn hơn tổng số lượng tồn kho hiện có (%s)!") % (
                    line.limit_qty, line.product_id.name, line.qty_in_stores
                ))
