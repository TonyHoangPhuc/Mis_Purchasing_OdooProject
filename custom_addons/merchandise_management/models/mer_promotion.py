import base64
import io

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MerPromotion(models.Model):
    _name = 'mer.promotion'
    _description = 'Kế hoạch khuyến mãi Merchandise'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tên chương trình', required=True)
    code = fields.Char(string='Mã khuyến mãi')
    
    state = fields.Selection([
        ('draft', 'Mới'),
        ('active', 'Đang chạy'),
        ('expired', 'Hết hạn'),
        ('cancel', 'Hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    date_start = fields.Date(string='Ngày bắt đầu', default=fields.Date.today)
    date_end = fields.Date(string='Ngày kết thúc')
    
    description = fields.Text(string='Mô tả chi tiết')
    
    product_ids = fields.Many2many('product.product', string='Sản phẩm áp dụng')
    discount_rate = fields.Float(string='Mức giảm (%)')
    
    # Bổ sung các trường Mới
    target_store_ids = fields.Many2many('res.partner', string='Cửa hàng áp dụng')
    excel_template = fields.Binary(string='File Excel mẫu', attachment=True)
    excel_template_name = fields.Char(string='Tên file Excel')

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
            # Đọc từ dòng 2 để bỏ qua tiêu đề ở dòng 1
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if row and row[0]: # Giả định Cột 1 là SKU (default_code)
                    product_codes.append(str(row[0]).strip())
                    
            if not product_codes:
                raise UserError(_("Không tìm thấy mã sản phẩm nào ở Cột số 1 trong file Excel."))
                
            products = self.env['product.product'].search([('default_code', 'in', product_codes)])
            
            if not products:
                raise UserError(_("Không tìm thấy bất kỳ sản phẩm nào có Mã SKU khớp với file tải lên."))
                
            # Đè danh sách sản phẩm mới vào
            self.product_ids = [(6, 0, products.ids)]
            
            # Cảnh báo mã không tìm thấy
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

    def action_activate(self):
        for promotion in self:
            # Chặn lỗi nếu chưa điền đủ thông tin
            if not promotion.product_ids:
                raise UserError(_("Bạn chưa chọn bất kỳ sản phẩm nào để áp dụng khuyến mãi!"))
            if not promotion.target_store_ids:
                raise UserError(_("Vui lòng chọn ít nhất một Cửa hàng áp dụng để gửi thông báo!"))
            if promotion.discount_rate <= 0:
                raise UserError(_("Mức giảm giá phải lớn hơn 0%%!"))

            promotion.write({'state': 'active'})
            
            for product in promotion.product_ids:
                discount_amount = product.lst_price * (promotion.discount_rate / 100.0)
                product.current_promotion_price = product.lst_price - discount_amount
                    
            # Tự động add các Cửa hàng vào danh sách Followers để họ nhận được Notification chuông đỏ
            promotion.message_subscribe(partner_ids=promotion.target_store_ids.ids)
            
            # Gửi tin nhắn nội bộ ghim trên hệ thống tới đại diện Cửa hàng
            message_body = _(
                "THÔNG BÁO KHUYẾN MÃI MỚI\n"
                "- Tên chương trình: %s\n"
                "- Mã KM: %s\n"
                "- Mức giảm: %s%%\n"
                "- Thời hạn: Từ %s đến %s\n"
                "Hệ thống đã cập nhật giá mới cho các sản phẩm liên quan. Vui lòng các Cửa hàng kiểm tra!"
            ) % (
                promotion.name, 
                promotion.code or '---', 
                promotion.discount_rate,
                promotion.date_start,
                promotion.date_end or 'Không thời hạn'
            )
            
            promotion.message_post(
                body=message_body,
                message_type='comment', # Đổi sang comment để dễ theo dõi hơn
                subtype_xmlid='mail.mt_comment',
                partner_ids=promotion.target_store_ids.ids
            )

    def action_expire(self):
        self.write({'state': 'expired'})
        for promotion in self:
            for product in promotion.product_ids:
                product.current_promotion_price = 0.0

