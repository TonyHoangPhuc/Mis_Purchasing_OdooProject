from odoo import api, fields, models, _
from collections import defaultdict

class SaleOrder(models.Model):
    _inherit = "sale.order"

    store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng bán",
        tracking=True,
    )

    @api.onchange('store_id')
    def _onchange_store_id_update_warehouse(self):
        """Tự động cập nhật Kho của đơn hàng theo Cửa hàng được chọn"""
        if self.store_id and self.store_id.warehouse_id:
            self.warehouse_id = self.store_id.warehouse_id
    store_stock_location_id = fields.Many2one(
        "stock.location",
        string="Vị trí tồn cửa hàng",
        related="warehouse_id.lot_stock_id",
        readonly=True,
    )
    x_available_product_ids = fields.Many2many(
        "product.product",
        compute="_compute_store_available_products",
        string="Sản phẩm có sẵn tại cửa hàng",
    )

    def _get_sale_store(self):
        self.ensure_one()
        return self.store_id or self.warehouse_id.store_record_id

    def _get_sale_store_products(self):
        self.ensure_one()
        store = self._get_sale_store()
        if not store:
            return self.env["product.product"]
        active_products = store.product_line_ids.filtered("active").mapped("product_id")
        if not active_products or not store.warehouse_id or not store.warehouse_id.lot_stock_id:
            return self.env["product.product"]
        return active_products

    @api.depends("store_id", "warehouse_id")
    def _compute_store_available_products(self):
        for order in self:
            order.x_available_product_ids = order._get_sale_store_products()

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        # Không tự động kết thúc KM ở đây nữa, vì ta chỉ trừ khi đã giao hàng thực tế
        return res

    @api.onchange('order_line')
    def _onchange_order_line_promotion_split(self):
        """Logic tách dòng KM ở cấp độ đơn hàng để đảm bảo UI tự cập nhật dòng mới"""
        # Tránh đệ quy vô tận
        if self._context.get('skip_promo_split'):
            return

        new_lines_to_add = []
        warnings = []

        for line in self.order_line:
            if not line.product_id or line.product_uom_qty <= 0:
                continue
            
            # Chỉ xử lý các dòng chưa bị tách (không có promotion_line_id hoặc đang ở trạng thái nháp)
            promo_line = line.product_id.current_promotion_line_id
            if promo_line and promo_line.promotion_id.state == 'active':
                # Kiểm tra cửa hàng
                store = self._get_sale_store()
                if promo_line.promotion_id.target_store_ids and store.warehouse_id not in promo_line.promotion_id.target_store_ids:
                    continue

                # Gán promotion_line_id nếu chưa có
                if not line.promotion_line_id:
                    line.promotion_line_id = promo_line

                if promo_line.limit_qty > 0:
                    # Tính toán số lượng đang có ở các dòng khác TRONG CÙNG ĐƠN HÀNG này
                    other_lines = self.order_line.filtered(
                        lambda l: l != line and l.product_id == line.product_id and l.promotion_line_id == promo_line
                    )
                    other_lines_qty = sum(other_lines.mapped('product_uom_qty'))

                    # Tính toán số lượng đã "giữ chỗ" bởi các đơn hàng đã xác nhận KHÁC
                    reserved_elsewhere = sum(self.env['sale.order.line'].sudo().search([
                        ('promotion_line_id', '=', promo_line.id),
                        ('state', 'in', ['sale', 'done']),
                        ('order_id', '!=', self._origin.id if self._origin else self.id)
                    ]).mapped('product_uom_qty'))

                    actual_remaining = max(0.0, promo_line.limit_qty - reserved_elsewhere - other_lines_qty)

                    if line.product_uom_qty > actual_remaining:
                        excess = line.product_uom_qty - actual_remaining
                        
                        if actual_remaining > 0:
                            # Tách dòng: Giảm số lượng dòng hiện tại và chuẩn bị thêm dòng mới
                            line.product_uom_qty = actual_remaining
                            line.price_unit = line.product_id.current_promotion_price
                            
                            new_lines_to_add.append({
                                'product_id': line.product_id.id,
                                'product_uom_qty': excess,
                                'price_unit': line.product_id.lst_price,
                                'promotion_line_id': False,
                                'sale_store_id': store.id,
                            })
                            warnings.append(_("Sản phẩm '%s' chỉ còn %s suất KM. Đã tách %s sản phẩm sang dòng mới giá gốc.") % (line.product_id.name, actual_remaining, excess))
                        else:
                            # Hết sạch suất: Chuyển cả dòng về giá gốc
                            line.price_unit = line.product_id.lst_price
                            line.promotion_line_id = False
                            warnings.append(_("Sản phẩm '%s' đã hết suất Khuyến mãi. Tự động áp dụng giá gốc.") % line.product_id.name)
                    else:
                        # Vẫn trong định mức: Áp dụng giá KM
                        line.price_unit = line.product_id.current_promotion_price
                else:
                    # Không giới hạn số lượng: Áp dụng giá KM
                    line.price_unit = line.product_id.current_promotion_price
            else:
                # Không có KM: Áp dụng giá gốc
                if line.promotion_line_id:
                    line.price_unit = line.product_id.lst_price
                    line.promotion_line_id = False

        if new_lines_to_add:
            # Thêm các dòng mới vào collection
            # Sử dụng context để tránh lặp lại logic
            for vals in new_lines_to_add:
                self.with_context(skip_promo_split=True).order_line = [(0, 0, vals)]
            
            return {
                'warning': {
                    'title': _("Thông báo Khuyến mãi"),
                    'message': "\n".join(warnings)
                }
            }

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sale_store_id = fields.Many2one(
        "store.store",
        related="order_id.store_id",
        string="Cửa hàng",
        store=True,
    )
    promotion_line_id = fields.Many2one(
        "mer.promotion.line",
        string="Chương trình KM",
        help="Chương trình khuyến mãi đang áp dụng cho dòng này",
    )
    purchase_price = fields.Float(string="Giá vốn")
    x_mer_margin = fields.Float(string="Lợi nhuận gộp", compute="_compute_mer_margin", store=True)
    x_mer_margin_percent = fields.Float(string="Tỷ suất LN (%)", compute="_compute_mer_margin", store=True)

    @api.depends('price_subtotal', 'purchase_price', 'product_uom_qty')
    def _compute_mer_margin(self):
        for line in self:
            cost = line.purchase_price or line.product_id.standard_price or 0.0
            total_cost = cost * line.product_uom_qty
            line.x_mer_margin = line.price_subtotal - total_cost
            line.x_mer_margin_percent = (line.x_mer_margin / line.price_subtotal * 100.0) if line.price_subtotal else 0.0

    @api.onchange("product_id")
    def _onchange_product_id_store_filter(self):
        if self.order_id.store_id:
            available_products = self.order_id._get_sale_store_products()
            if self.product_id and self.product_id not in available_products:
                return {
                    "warning": {
                        "title": _("Sản phẩm không có sẵn"),
                        "message": _(
                            "Sản phẩm %s không có sẵn tại cửa hàng %s."
                        )
                        % (self.product_id.display_name, self.order_id.store_id.name),
                    }
                }

    @api.depends('product_id', 'product_uom_id', 'product_uom_qty', 'sale_store_id', 'promotion_line_id', 'promotion_line_id.promotion_id.state', 'state')
    def _compute_price_unit(self):
        super()._compute_price_unit()
        for line in self:
            if line.state not in ['draft', 'sent']:
                continue

            if line.promotion_line_id and line.promotion_line_id.promotion_id.state == 'active':
                discount = line.promotion_line_id.discount_rate
                line.price_unit = line.product_id.lst_price * (1 - (discount / 100.0))
            elif line.sale_store_id and line.product_id and line.product_id.current_promotion_price > 0:
                line.price_unit = line.product_id.lst_price
