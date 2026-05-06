from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError


class MerPromotionLine(models.Model):
    _name = 'mer.promotion.line'
    _description = 'Promotion Line'

    promotion_id = fields.Many2one('mer.promotion', string='Promotion', ondelete='cascade')
    warehouse_id = fields.Many2one('stock.warehouse', string='Cửa hàng', required=True)
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    discount_rate = fields.Float(string='Mức giảm (%)')
    qty_in_stores = fields.Float(string='Tồn tại Cửa hàng', compute='_compute_qty_in_stores')
    default_code = fields.Char(related='product_id.default_code', string='SKU')
    lst_price = fields.Float(related='product_id.lst_price', string='List Price')
    limit_qty = fields.Float(string='SL KM Tối đa', default=0.0, help='Giới hạn số lượng được bán với giá KM (Để 0 là không giới hạn)')
    sold_qty = fields.Float(string='Đã bán', compute='_compute_sold_qty', copy=False)
    reserved_qty = fields.Float(string='Giữ chỗ', compute='_compute_reserved_qty')
    remaining_qty = fields.Float(string='Còn lại', compute='_compute_remaining_qty')

    def _get_valid_target_warehouses(self):
        self.ensure_one()
        valid_warehouses = self.env['stock.warehouse']

        if not self.product_id or not self.promotion_id.target_store_ids:
            return valid_warehouses

        for warehouse in self.promotion_id.target_store_ids.filtered('lot_stock_id'):
            quants = self.env['stock.quant'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ('quantity', '>', 0),
            ])
            if sum(quants.mapped('quantity')) > 0:
                valid_warehouses |= warehouse

        return valid_warehouses

    def _get_sibling_product_warehouse_ids(self):
        self.ensure_one()
        sibling_lines = self.promotion_id.line_ids.filtered(
            lambda line: line != self and line.product_id == self.product_id and line.warehouse_id
        )
        return set(sibling_lines.mapped('warehouse_id').ids)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Tự động tách 1 sản phẩm thành nhiều dòng theo từng cửa hàng còn tồn."""
        if not self.product_id or not self.promotion_id.target_store_ids:
            return

        valid_warehouses = self._get_valid_target_warehouses()

        # Nếu không cửa hàng nào có hàng, thông báo lỗi và xóa sản phẩm vừa chọn
        if not valid_warehouses:
            product_name = self.product_id.name
            self.product_id = False
            self.warehouse_id = False
            return {
                'warning': {
                    'title': _('Hết hàng tồn kho'),
                    'message': _('Sản phẩm "%s" hiện không còn tồn kho tại (các) cửa hàng bạn đã chọn ở trên. Vui lòng kiểm tra lại.') % product_name
                }
            }

        sibling_warehouse_ids = self._get_sibling_product_warehouse_ids()
        available_warehouses = valid_warehouses.filtered(lambda wh: wh.id not in sibling_warehouse_ids)

        if not available_warehouses:
            product_name = self.product_id.name
            self.product_id = False
            self.warehouse_id = False
            return {
                'warning': {
                    'title': _('Đã có đủ dòng cửa hàng'),
                    'message': _('Sản phẩm "%s" đã được tạo đủ cho các cửa hàng còn tồn trong chương trình này.') % product_name
                }
            }

        current_warehouse = self.warehouse_id if (
            self.warehouse_id
            and self.warehouse_id in valid_warehouses
            and self.warehouse_id.id not in sibling_warehouse_ids
        ) else self.env['stock.warehouse']

        if not current_warehouse:
            current_warehouse = available_warehouses[0]

        self.warehouse_id = current_warehouse

        extra_commands = []
        for warehouse in available_warehouses.filtered(lambda wh: wh != current_warehouse):
            extra_commands.append(Command.create({
                'product_id': self.product_id.id,
                'warehouse_id': warehouse.id,
                'discount_rate': self.discount_rate or 0.0,
                'limit_qty': self.limit_qty or 0.0,
            }))

        if extra_commands:
            self.promotion_id.update({'line_ids': extra_commands})

    @api.constrains('promotion_id', 'product_id', 'warehouse_id')
    def _check_duplicate_product_warehouse(self):
        for line in self.filtered(lambda rec: rec.promotion_id and rec.product_id and rec.warehouse_id):
            duplicate_lines = line.promotion_id.line_ids.filtered(
                lambda other: other != line
                and other.product_id == line.product_id
                and other.warehouse_id == line.warehouse_id
            )
            if duplicate_lines:
                raise ValidationError(
                    _(
                        'Sản phẩm "%s" đã tồn tại tại cửa hàng "%s" trong chương trình này.'
                    ) % (line.product_id.display_name, line.warehouse_id.display_name)
                )

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

    @api.depends('product_id', 'warehouse_id')
    def _compute_qty_in_stores(self):
        for line in self:
            if not line.warehouse_id or not line.product_id:
                line.qty_in_stores = 0.0
                continue

            # 1. Lấy tồn thực tế tại Cửa hàng
            main_location = line.warehouse_id.lot_stock_id
            quants = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', 'child_of', main_location.id),
                ('quantity', '>', 0),
            ])
            physical_qty = sum(quants.mapped('quantity'))

            # 2. Tìm các dòng KM đang chạy khác (cùng sản phẩm, cùng cửa hàng)
            other_active_lines = self.env['mer.promotion.line'].search([
                ('promotion_id.state', '=', 'active'),
                ('product_id', '=', line.product_id.id),
                ('warehouse_id', '=', line.warehouse_id.id),
                ('id', '!=', line._origin.id if hasattr(line, '_origin') else line.id),
            ])
            reserved_by_other_promos = sum(other_active_lines.mapped('remaining_qty'))

            # 3. Tồn khả dụng KM = Tồn thực tế - Đã giữ chỗ ở các KM khác
            line.qty_in_stores = max(0.0, physical_qty - reserved_by_other_promos)
