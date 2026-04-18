import base64
import io

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta

# Quản lý chương trình khuyến mãi và tự động cập nhật giá
class MerPromotion(models.Model):
    _name = 'mer.promotion'
    _description = 'Kế hoạch khuyến mãi Merchandise'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tên chương trình', required=True)
    code = fields.Char(string='Mã khuyến mãi', required=True, readonly=True, copy=False, default=lambda self: _('New'))
    
    state = fields.Selection([
        ('draft', 'Mới'),
        ('active', 'Đang chạy'),
        ('expired', 'Hết hạn')
    ], string='Trạng thái', default='draft', tracking=True)
    
    date_start = fields.Date(string='Ngày bắt đầu', default=fields.Date.today, required=True)
    date_end = fields.Date(string='Ngày kết thúc')
    
    description = fields.Text(string='Mô tả chi tiết')
    
    line_ids = fields.One2many('mer.promotion.line', 'promotion_id', string='Chi tiết sản phẩm')
    product_ids = fields.Many2many('product.product', string='Sản phẩm áp dụng', compute='_compute_product_ids', store=True) # Giữ để tương thích logic cũ
    
    # Các trường mở rộng Merchandise
    target_store_ids = fields.Many2many('stock.warehouse', string='Cửa hàng áp dụng')
    
    # Hiển thị lot_ids từ lines
    def _compute_product_ids(self):
        for rec in self:
            rec.product_ids = rec.line_ids.mapped('product_id')

    # Trường bổ sung cho KM hàng sắp hết hạn
    is_expiry_promo = fields.Boolean(string='KM Hàng sắp hết hạn', default=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('mer.promotion') or _('New')
        return super(MerPromotion, self).create(vals_list)
    
    lot_id = fields.Many2one('stock.lot', string='Lô hàng áp dụng')
    lot_ids = fields.Many2many('stock.lot', string='Danh sách lô hàng áp dụng')


    # Tính năng thủ công: Quét lô hàng cận hạn vào chương trình hiện tại
    def action_fetch_expiry_lots(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Chỉ có thể lấy thêm hàng khi chương trình đang ở trạng thái Nháp."))
            
        today = fields.Date.today()
        # 1. Xác định chính xác các Kho là Cửa hàng
        store_warehouses = self.env['stock.warehouse'].search([('mis_role', '=', 'store')])
        store_locations = store_warehouses.mapped('lot_stock_id')
        
        # 2. Chỉ quét tồn kho thực tế nằm tại các Địa điểm chính cửa hàng (ví dụ: 1/Stock)
        store_quants = self.env['stock.quant'].search([
            ('quantity', '>', 0),
            ('location_id', 'child_of', store_locations.ids),
            ('lot_id', '!=', False),
            ('lot_id.expiration_date', '>', today),
            ('lot_id.expiration_date', '<=', today + timedelta(days=90))
        ])

        lots_in_stores = store_quants.mapped('lot_id')
        
        valid_lots = lots_in_stores.filtered(
            lambda l: l.expiration_date and fields.Date.to_date(l.expiration_date) <= today + timedelta(days=l.product_id.x_mer_expiry_days or 30)
        )
        
        line_vals = []
        warehouse_ids = self.target_store_ids.ids
        
        # Lấy danh sách ID đã có sẵn trong bảng
        existing_product_ids = self.line_ids.mapped('product_id').ids
        seen_products = set(existing_product_ids)
        
        for lot in valid_lots:
            lot_locations = store_quants.filtered(lambda q: q.lot_id == lot).mapped('location_id')
            lot_warehouses = lot_locations.mapped('warehouse_id')
            
            # Thêm vào lines nếu chưa có, kèm theo mức giảm của sản phẩm đó
            if lot.product_id.id not in seen_products:
                line_vals.append((0, 0, {
                    'product_id': lot.product_id.id,
                    'discount_rate': lot.product_id.x_mer_expiry_discount or 20.0
                }))
                seen_products.add(lot.product_id.id)
            
            warehouse_ids.extend(lot_warehouses.ids)
        
        if line_vals or valid_lots:
            # Tính tổng tồn của toàn bộ sản phẩm (không chỉ riêng các lô cận hạn) để khớp với bảng bên dưới
            # Xử lý mô tả: Xóa kết quả quét cũ nếu có
            new_description = self.description or ''
            if "--- Cập nhật:" in new_description:
                new_description = new_description.split("--- Cập nhật:")[0].strip()

            self.write({
                'is_expiry_promo': True,
                'line_ids': line_vals,
                'lot_ids': [(6, 0, valid_lots.ids)],
                'target_store_ids': [(6, 0, list(set(warehouse_ids)))],
            })
            # Sau khi ghi xong, tính lại tổng tồn dựa trên các dòng thực tế
            total_qty = sum(self.line_ids.mapped('qty_in_stores'))
            product_details = "\n".join([_(" • %s: %s") % (l.product_id.name, l.qty_in_stores) for l in self.line_ids])
            msg = _("--- Cập nhật: Tìm thấy %s lô hàng với tổng tồn %s tại %s.\n%s") % (
                len(valid_lots), total_qty, ", ".join(store_locations.mapped('display_name')), product_details
            )
            self.write({'description': (new_description + "\n" + msg).strip()})
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        else:
            raise UserError(_("Không tìm thấy lô hàng nào sắp hết hạn trong kho."))

    # Kiểm tra ngày bắt đầu/kết thúc
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_start > record.date_end:
                raise UserError(_("Ngày bắt đầu không thể sau ngày kết thúc."))

    # Cập nhật giá sản phẩm thông minh (Batch & Best Price)
    @api.model
    def _update_product_prices(self, products=None):
        today = fields.Date.today()
        
        # 1. Tìm tất cả KM đang chạy (có hiệu lực)
        active_promotions = self.search([
            ('state', '=', 'active'),
            ('date_start', '<=', today),
            '|', ('date_end', '>=', today), ('date_end', '=', False)
        ])
        
        # 2. Tính toán mức giá KM thấp nhất cho mỗi sản phẩm từ TẤT CẢ các KM đang active
        promo_data = {}
        for promo in active_promotions:
            for line in promo.line_ids:
                if not line.product_id:
                    continue
                price = line.product_id.lst_price * (1 - (line.discount_rate / 100.0))
                if line.product_id.id not in promo_data or price < promo_data[line.product_id.id]:
                    promo_data[line.product_id.id] = price
        
        # 3. Xác định danh sách sản phẩm cần cập nhật
        # Nếu không truyền vào products, chúng ta sẽ quét toàn bộ sản phẩm đang có giá KM để reset nếu cần
        if products is None:
            products = self.env['product.product'].search(['|', ('current_promotion_price', '>', 0), ('id', 'in', list(promo_data.keys()))])

        # 4. Ghi đè giá KM mới
        for product in products:
            new_price = promo_data.get(product.id, 0.0)
            if product.current_promotion_price != new_price:
                product.current_promotion_price = new_price

    # Scheduler định kỳ cập nhật KM
    @api.model
    def _run_promotion_scheduler(self):
        today = fields.Date.today()
        
        # 1. Tự động chuyển các KM quá hạn sang Expired
        expired_promos = self.search([
            ('state', '=', 'active'),
            ('date_end', '<', today)
        ])
        if expired_promos:
            expired_promos.write({'state': 'expired'})

        # 3. Quét tạo mới KM hàng cận hạn
        self._generate_expiry_promotions()

        # 4. Cập nhật lại toàn bộ bảng giá sản phẩm
        self._update_product_prices()

    def action_run_scheduler_manually(self):
        """Hàm cho phép admin chạy quét thủ công từ giao diện"""
        self._run_promotion_scheduler()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': 'Đã hoàn thành quét hàng cận date toàn hệ thống!',
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    # Logic tự động tạo KM cho hàng sắp hết hạn (Gộp theo đợt)
    @api.model
    def _generate_expiry_promotions(self):
        today = fields.Date.today()
        
        # 1. Xác định các Kho Cửa hàng và Địa điểm chính
        store_warehouses = self.env['stock.warehouse'].search([('mis_role', '=', 'store')])
        store_locations = store_warehouses.mapped('lot_stock_id')
        
        # 2. Tìm quants nội bộ có lot sắp hết hạn thuộc các Địa điểm cửa hàng
        store_quants = self.env['stock.quant'].search([
            ('quantity', '>', 0),
            ('location_id', 'child_of', store_locations.ids),
            ('lot_id', '!=', False),
            ('lot_id.expiration_date', '>', today),
            ('lot_id.expiration_date', '<=', today + timedelta(days=90))
        ])
        
        lots_in_stores = store_quants.mapped('lot_id')
        
        products_map = [] 
        total_store_qty = 0
        
        for lot in lots_in_stores:
            # Lọc lại theo cấu hình riêng của từng SP (Chuyển Datetime sang Date để so sánh)
            expiry_days = lot.product_id.x_mer_expiry_days or 30
            lot_date = fields.Date.to_date(lot.expiration_date)
            if not lot_date or lot_date > today + timedelta(days=expiry_days):
                continue

            # Kiểm tra trùng lặp
            domain = [
                ('state', 'in', ['draft', 'active']),
                '|', ('lot_id', '=', lot.id), ('lot_ids', 'in', [lot.id])
            ]
            if not self.search_count(domain):
                # Warehouse tương ứng của lot này (chỉ ở các store)
                lot_quants = store_quants.filtered(lambda q: q.lot_id == lot)
                lot_locations = lot_quants.mapped('location_id')
                lot_warehouses = lot_locations.mapped('warehouse_id')
                
                if lot_warehouses:
                    qty = sum(lot_quants.mapped('quantity'))
                    total_store_qty += qty
                    products_map.append({
                        'product_id': lot.product_id,
                        'warehouses': lot_warehouses,
                        'lot_id': lot.id,
                        'qty': qty
                    })

        if products_map:
            # Tạo 1 đợt khuyến mãi tổng hợp cho các sản phẩm cận hạn
            promo_name = _("KM Hàng cận hạn - %s") % today.strftime('%d/%m/%Y')
            
            all_lot_ids = [p['lot_id'] for p in products_map]
            all_warehouse_ids = []
            line_vals = []
            seen_products = set()
            for p in products_map:
                all_warehouse_ids.extend(p['warehouses'].ids)
                if p['product_id'].id not in seen_products:
                    line_vals.append((0, 0, {
                        'product_id': p['product_id'].id,
                        'discount_rate': 0.0 # Để trống mức giảm để người dùng tự điền
                    }))
                    seen_products.add(p['product_id'].id)
            
            # Tạo bản ghi KM
            new_promo = self.create({
                'name': promo_name,
                'code': "EXP-%s" % today.strftime('%Y%m%d%H%M'), 
                'is_expiry_promo': True,
                'line_ids': line_vals,
                'lot_ids': [(6, 0, list(set(all_lot_ids)))],
                'target_store_ids': [(6, 0, list(set(all_warehouse_ids)))],
                'date_start': today,
                'date_end': False, # Để trống ngày kết thúc
            })
            
            # Sau khi tạo xong, tính lại tổng tồn kho thực tế của các dòng để ghi vào mô tả
            total_qty_actual = sum(new_promo.line_ids.mapped('qty_in_stores'))
            product_details = "\n".join([_(" • %s: %s") % (l.product_id.name, l.qty_in_stores) for l in new_promo.line_ids])
            msg = _("--- Cập nhật: Tìm thấy %s lô hàng với tổng tồn %s tại %s.\n%s") % (
                len(products_map), total_qty_actual, ", ".join(store_locations.mapped('display_name')), product_details
            )
            new_promo.write({'description': msg})

    # Chỉ cho phép xóa khi chưa kích hoạt
    def unlink(self):
        for record in self:
            if record.state == 'active':
                raise UserError(_("Không thể xóa: Chương trình '%s' đang ở trạng thái 'Đang chạy'. Bạn phải kết thúc nó trước.") % record.name)
        return super(MerPromotion, self).unlink()

    # Kích hoạt chương trình và gửi thông báo
    def action_activate(self):
        for promotion in self:
            if not promotion.code:
                raise UserError(_("Vui lòng nhập Mã khuyến mãi trước khi kích hoạt."))
            if not promotion.line_ids:
                raise UserError(_("Vui lòng thêm ít nhất một sản phẩm!"))
            
            # Kiểm tra mức giảm giá của từng sản phẩm
            for line in promotion.line_ids:
                if line.discount_rate <= 0:
                    raise UserError(_("Vui lòng điền mức giảm giá cho sản phẩm '%s'.") % line.product_id.name)
            if not promotion.target_store_ids:
                raise UserError(_("Vui lòng chọn ít nhất một Cửa hàng áp dụng!"))
            
            # Kiểm tra logic ngày tháng ngay tại đây
            if not promotion.date_end:
                raise UserError(_("Vui lòng điền Ngày kết thúc trước khi kích hoạt chương trình."))
            if promotion.date_start and promotion.date_start > promotion.date_end:
                raise UserError(_("Lỗi ngày tháng: Ngày bắt đầu (%s) không thể sau ngày kết thúc (%s).") % (promotion.date_start, promotion.date_end))

            promotion.write({'state': 'active'})
            
            # Cập nhật giá sản phẩm ngay lập tức
            # Sử dụng line_ids trực tiếp để tránh lỗi cache
            products = promotion.line_ids.mapped('product_id')
            self._update_product_prices(products=products)
            
            # Gửi thông báo
            if promotion.state == 'active': # Chỉ gửi nếu chưa bị chuyển sang expired ngay
                store_partners = promotion.target_store_ids.mapped('partner_id')
                if store_partners:
                    promotion.message_subscribe(partner_ids=store_partners.ids)
                    
                    # Sử dụng Markup để render HTML
                    from markupsafe import Markup
                    
                    # Tạo danh sách sản phẩm và mức giảm để hiện trong thông báo
                    line_details = Markup("").join([
                        Markup("<li>• %s: <span style='color: #16a34a; font-weight: bold;'>%s%%</span></li>") % (line.product_id.name, line.discount_rate)
                        for line in promotion.line_ids
                    ])

                    content = Markup(
                        "<div style='background-color: #f0fdf4; border-left: 5px solid #22c55e; padding: 15px; border-radius: 4px; font-family: sans-serif;'>"
                            "<h3 style='margin-top: 0; color: #166534; border-bottom: 1px solid #bbf7d0; padding-bottom: 8px;'>📢 %s</h3>"
                            "<ul style='list-style: none; padding: 0; margin: 10px 0; color: #15803d; line-height: 1.6;'>"
                                "<li><b>🏷️ %s:</b> %s</li>"
                                "<li><b>🔢 %s:</b> %s</li>"
                                "<li><b>📦 %s:</b> %s sản phẩm</li>"
                                "<li><b>📅 %s:</b> Từ <span style='font-weight: bold;'>%s</span> đến <span style='font-weight: bold;'>%s</span></li>"
                            "</ul>"
                            "<div style='margin-top: 10px; color: #15803d;'>"
                                "<b>📉 Chi tiết mức giảm:</b>"
                                "<ul style='margin-top: 5px; padding-left: 15px; list-style: none;'>%s</ul>"
                            "</div>"
                            "<p style='margin-bottom: 0; font-style: italic; color: #166534; font-size: 0.9em; border-top: 1px dashed #bbf7d0; pt: 8px;'>"
                                "💡 <i>%s</i>"
                            "</p>"
                        "</div>"
                    ) % (
                        _("THÔNG BÁO KHUYẾN MÃI MỚI"),
                        _("Tên chương trình"), promotion.name,
                        _("Mã KM"), promotion.code or '---',
                        _("Số lượng"), len(promotion.line_ids),
                        _("Thời hạn"), promotion.date_start, promotion.date_end or _('Không thời hạn'),
                        line_details,
                        _("Lưu ý: Hệ thống sẽ tự động cập nhật giá mới cho các sản phẩm liên quan vào đúng ngày bắt đầu. Vui lòng các Cửa hàng kiểm tra!")
                    )
                    promotion.message_post(body=content, partner_ids=store_partners.ids)

    # Kết thúc sớm chương trình KM
    def action_expire(self):
        for record in self:
            products = record.product_ids
            record.write({'state': 'expired'})
            self._update_product_prices(products=products)
class MerPromotionLineLegacy(models.Model):
    _register = False
    _name = 'mer.promotion.line.legacy'
    _description = 'Chi tiết dòng Khuyến mãi'

    promotion_id = fields.Many2one('mer.promotion', string='Chương trình KM', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    discount_rate = fields.Float(string='Mức giảm (%)')
    
    # Cột quan trọng: Tính toán tồn kho dựa trên Warehouse của chương trình
    qty_in_stores = fields.Float(string='Tồn tại Cửa hàng', compute='_compute_qty_in_stores')
    
    # Đồng bộ thông tin cơ bản của SP
    default_code = fields.Char(related='product_id.default_code', string='Mã SKU')
    lst_price = fields.Float(related='product_id.lst_price', string='Giá gốc')

    @api.depends('product_id', 'promotion_id.target_store_ids')
    def _compute_qty_in_stores(self):
        for line in self:
            warehouses = line.promotion_id.target_store_ids
            if not warehouses:
                line.qty_in_stores = 0.0
                continue
            
            # Quét tồn kho thực tế chỉ trong các Kho được áp dụng
            quants = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id.warehouse_id', 'in', warehouses.ids),
                ('quantity', '>', 0)
            ])
            line.qty_in_stores = sum(quants.mapped('quantity'))



