from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_mer_stop_ordering = fields.Boolean(
        string='Dừng đặt hàng',
        help='Nếu được chọn, sản phẩm này sẽ bị chặn khi tạo Order mua hàng (PO).',
        default=False
    )
    
    x_mer_stock_status = fields.Selection([
        ('normal', 'Bình thường'),
        ('overstock', 'Thừa hàng (Overstock)'),
        ('understock', 'Thiếu hàng (Understock)'),
        ('slow_moving', 'Hàng tồn lâu (Slow Moving)')
    ], string='Trạng thái tồn kho (Mer)', default='normal')

    # Bổ sung trường này để khắc phục lỗi OwlError do view cũ yêu cầu
    current_promotion_price = fields.Float(string='Giá khuyến mãi hiện tại', company_dependent=True)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    current_promotion_price = fields.Float(related='product_tmpl_id.current_promotion_price', readonly=False)

