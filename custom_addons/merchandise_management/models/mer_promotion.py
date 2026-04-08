import base64
import io

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None

from odoo import models, fields, api, _
from odoo.exceptions import UserError

# Quản lý chương trình khuyến mãi và tự động cập nhật giá
class MerPromotion(models.Model):
    _name = 'mer.promotion'
    _description = 'Kế hoạch khuyến mãi Merchandise'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tên chương trình', required=True)
    code = fields.Char(string='Mã khuyến mãi', required=True)
    
    state = fields.Selection([
        ('draft', 'Mới'),
        ('active', 'Đang chạy'),
        ('expired', 'Hết hạn')
    ], string='Trạng thái', default='draft', tracking=True)
    
    date_start = fields.Date(string='Ngày bắt đầu', default=fields.Date.today, required=True)
    date_end = fields.Date(string='Ngày kết thúc', required=True)
    
    description = fields.Text(string='Mô tả chi tiết')
    
    product_ids = fields.Many2many('product.product', string='Sản phẩm áp dụng')
    discount_rate = fields.Float(string='Mức giảm (%)')
    
    # Các trường mở rộng Merchandise
    target_store_ids = fields.Many2many('stock.warehouse', string='Cửa hàng áp dụng')
    excel_template = fields.Binary(string='File Excel mẫu', attachment=True)
    excel_template_name = fields.Char(string='Tên file Excel')

    # Nhập SKU từ file Excel
    def action_import_excel(self):
        if not self.excel_template:
            raise UserError(_("Vui lòng tải lên file Excel trước khi bấm Nhập."))
            
        if not load_workbook:
            raise UserError(_("Thư viện openpyxl chưa được cài đặt trên server."))

        try:
            file_content = base64.b64decode(self.excel_template)
            file_obj = io.BytesIO(file_content)
            wb = load_workbook(filename=file_obj, data_only=True)
            sheet = wb.active
            
            product_codes = []
            # Bỏ qua tiêu đề (dòng 1)
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if row and row[0]: # Cột 1 là SKU
                    product_codes.append(str(row[0]).strip())
                    
            if not product_codes:
                raise UserError(_("Không tìm thấy mã sản phẩm nào ở Cột số 1 trong file Excel."))
                
            products = self.env['product.product'].search([('default_code', 'in', product_codes)])
            
            if not products:
                raise UserError(_("Không tìm thấy bất kỳ sản phẩm nào có Mã SKU khớp với file tải lên."))
                
            # Cập nhật danh sách sản phẩm mới
            self.product_ids = [(6, 0, products.ids)]
            
            # Kiểm tra SKU không tồn tại
            found_codes = products.mapped('default_code')
            missing_codes = set(product_codes) - set(filter(None, found_codes))
            if missing_codes:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Cảnh báo nhập liệu',
                        'message': 'Đã nạp thành công! Nhưng các mã sau không khớp/không tồn tại trên hệ thống: %s' % ', '.join(missing_codes),
                        'sticky': False,
                        'type': 'warning',
                    }
                }
                
        except Exception as e:
            raise UserError(_("Lỗi đọc file Excel: %s") % str(e))

    # Kiểm tra ngày bắt đầu/kết thúc
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_start > record.date_end:
                raise UserError(_("Ngày bắt đầu không thể sau ngày kết thúc."))

    # Cập nhật giá sản phẩm theo ngày
    def _update_product_prices(self):
        today = fields.Date.today()
        for promotion in self:
            # Hết hạn nếu quá ngày kết thúc
            if promotion.state == 'active' and promotion.date_end and promotion.date_end < today:
                promotion.state = 'expired'
            
            is_active_period = promotion.state == 'active' and promotion.date_start <= today and (not promotion.date_end or promotion.date_end >= today)
            
            for product in promotion.product_ids:
                if is_active_period:
                    discount_amount = product.lst_price * (promotion.discount_rate / 100.0)
                    product.current_promotion_price = product.lst_price - discount_amount
                else:
                    product.current_promotion_price = 0.0

    # Scheduler định kỳ cập nhật KM
    @api.model
    def _run_promotion_scheduler(self):
        today = fields.Date.today()
        
        # Kích hoạt tự động các bản ghi mới đến ngày
        draft_promotions = self.search([
            ('state', '=', 'draft'),
            ('date_start', '<=', today),
            ('date_end', '>=', today)
        ])
        for promo in draft_promotions:
            # Kiểm tra nhanh tính hợp lệ trước khi tự kích hoạt
            if promo.code and promo.product_ids and promo.target_store_ids and promo.discount_rate > 0:
                promo.action_activate() # Tận dụng hàm kích hoạt có sẵn (đã bao gồm gửi thông báo)

        # Cập nhật giá cho các chương trình đang chạy
        active_promotions = self.search([('state', '=', 'active')])
        active_promotions._update_product_prices()

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
            if not promotion.product_ids:
                raise UserError(_("Bạn chưa chọn bất kỳ sản phẩm nào!"))
            if not promotion.target_store_ids:
                raise UserError(_("Vui lòng chọn ít nhất một Cửa hàng áp dụng!"))
            if promotion.discount_rate <= 0:
                raise UserError(_("Mức giảm giá phải lớn hơn 0%%!"))
            
            # Kiểm tra logic ngày tháng ngay tại đây
            if promotion.date_start and promotion.date_end and promotion.date_start > promotion.date_end:
                raise UserError(_("Lỗi ngày tháng: Ngày bắt đầu (%s) không thể sau ngày kết thúc (%s).") % (promotion.date_start, promotion.date_end))

            promotion.write({'state': 'active'})
            
            # Cập nhật giá sản phẩm ngay lập tức
            promotion._update_product_prices()
            
            # Gửi thông báo
            if promotion.state == 'active': # Chỉ gửi nếu chưa bị chuyển sang expired ngay
                store_partners = promotion.target_store_ids.mapped('partner_id')
                if store_partners:
                    promotion.message_subscribe(partner_ids=store_partners.ids)
                    
                    # Sử dụng Markup để render HTML
                    from markupsafe import Markup
                    
                    content = Markup(
                        "<div style='background-color: #f0fdf4; border-left: 5px solid #22c55e; padding: 15px; border-radius: 4px; font-family: sans-serif;'>"
                            "<h3 style='margin-top: 0; color: #166534; border-bottom: 1px solid #bbf7d0; padding-bottom: 8px;'>📢 %s</h3>"
                            "<ul style='list-style: none; padding: 0; margin: 10px 0; color: #15803d; line-height: 1.6;'>"
                                "<li><b>🏷️ %s:</b> %s</li>"
                                "<li><b>🔢 %s:</b> %s</li>"
                                "<li><b>📉 %s:</b> <span style='font-size: 1.1em; color: #16a34a;'>%s%%</span></li>"
                                "<li><b>📅 %s:</b> Từ <span style='font-weight: bold;'>%s</span> đến <span style='font-weight: bold;'>%s</span></li>"
                            "</ul>"
                            "<p style='margin-bottom: 0; font-style: italic; color: #166534; font-size: 0.9em; border-top: 1px dashed #bbf7d0; pt: 8px;'>"
                                "💡 <i>%s</i>"
                            "</p>"
                        "</div>"
                    ) % (
                        _("THÔNG BÁO KHUYẾN MÃI MỚI"),
                        _("Tên chương trình"), promotion.name,
                        _("Mã KM"), promotion.code or '---',
                        _("Mức giảm"), promotion.discount_rate,
                        _("Thời hạn"), promotion.date_start, promotion.date_end or _('Không thời hạn'),
                        _("Lưu ý: Hệ thống sẽ tự động cập nhật giá mới cho các sản phẩm liên quan vào đúng ngày bắt đầu. Vui lòng các Cửa hàng kiểm tra!")
                    )
                    promotion.message_post(body=content, partner_ids=store_partners.ids)

    # Kết thúc sớm chương trình KM
    def action_expire(self):
    # Kết thúc chương trình sớm và khôi phục giá gốc
        self.write({'state': 'expired'})
        self._update_product_prices()

