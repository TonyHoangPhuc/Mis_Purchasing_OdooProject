from odoo import models, fields, api

# Mở rộng thông tin sản phẩm chuẩn để phù hợp với nghiệp vụ Merchandise
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Cờ trạng thái: Dùng để chặn mua hàng khi sản phẩm có vấn đề (Ví dụ: lỗi NCC)
    x_mer_stop_ordering = fields.Boolean(
        string='Dừng đặt hàng',
        help='Nếu được chọn, sản phẩm này sẽ bị chặn khi tạo đơn mua hàng (PO).',
        default=False
    )
    
    # Phân loại tồn kho: Giúp nhân viên Merchandise dễ dàng lọc sản phẩm thừa/thiếu
    x_mer_stock_status = fields.Selection([
        ('normal', 'Bình thường'),
        ('overstock', 'Thừa hàng'),
        ('understock', 'Thiếu hàng'),
        ('slow_moving', 'Hàng tồn lâu')
    ], string='Trạng thái tồn kho (Mer)', default='normal')

    # Định nghĩa luồng giao hàng: Giúp PR tự động xác định NCC hoặc Kho tổng
    x_mer_supply_route = fields.Selection([
        ('warehouse', 'Kho Tổng'),
        ('supplier_direct', 'Trực tiếp từ NCC')
    ], string='Luồng cung ứng', default='warehouse', help='Hàng hóa được giao từ Kho tổng hoặc giao trực tiếp từ Nhà cung cấp đến cửa hàng.')

    # Trường lưu giá KM đang áp dụng (được Scheduler tự động cập nhật)
    current_promotion_price = fields.Float(string='Giá khuyến mãi hiện tại', company_dependent=True)
    current_promotion_line_id = fields.Many2one('mer.promotion.line', string='Dòng Khuyến mãi đang áp dụng', company_dependent=True)

    # Cấu hình KM hàng cận hạn riêng cho từng sản phẩm
    x_mer_expiry_days = fields.Integer(string='Ngày báo trước cận hạn', default=30, help="Số ngày trước khi hết hạn để bắt đầu chạy khuyến mãi.")
    x_mer_expiry_discount = fields.Float(string='% Giảm hàng cận hạn', default=20.0, help="Mức giảm giá mặc định khi sản phẩm rơi vào diện cận hạn.")

    # [NEW] Vòng đời SKU
    x_mer_sku_lifecycle = fields.Selection([
        ('new', 'Hàng mới (New)'),
        ('active', 'Đang kinh doanh (Active)'),
        ('slow', 'Bán chậm (Slow-moving)'),
        ('phase_out', 'Xả hàng (Phase-out)'),
        ('discontinued', 'Ngừng kinh doanh (Discontinued)')
    ], string='Vòng đời SKU', default='new', tracking=True)

    # [NEW] Phân loại ABC
    x_mer_abc_classification = fields.Selection([
        ('a', 'Nhóm A (Quan trọng nhất)'),
        ('b', 'Nhóm B (Trung bình)'),
        ('c', 'Nhóm C (Giá trị thấp)')
    ], string='Phân loại ABC', default='b')

# Đồng bộ hóa giá KM cho các biến thể sản phẩm
class ProductProduct(models.Model):
    _inherit = 'product.product'

    current_promotion_price = fields.Float(related='product_tmpl_id.current_promotion_price', readonly=False)
    current_promotion_line_id = fields.Many2one(related='product_tmpl_id.current_promotion_line_id', readonly=False)
