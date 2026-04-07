from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MerDiscrepancyReport(models.Model):
    _name = 'mer.discrepancy.report'
    _description = 'Báo cáo sai lệch hàng hóa'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã báo cáo', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    
    state = fields.Selection([
        ('draft', 'Mới'),
        ('reporting', 'Đang báo cáo'),
        ('solving', 'Đang giải quyết'),
        ('done', 'Hoàn tất'),
        ('cancel', 'Hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    date_discrepancy = fields.Date(string='Ngày ghi nhận', default=fields.Date.today)
    
    user_id = fields.Many2one('res.users', string='Người báo cáo', default=lambda self: self.env.user)
    
    picking_id = fields.Many2one('stock.picking', string='Phiếu kho liên quan')
    purchase_id = fields.Many2one('purchase.order', string='Đơn mua hàng liên quan')
    
    product_id = fields.Many2one('product.product', string='Sản phẩm sai lệch', required=True)
    expected_qty = fields.Float(string='Số lượng theo chứng từ')
    actual_qty = fields.Float(string='Số lượng nhận thực tế')
    difference_qty = fields.Float(string='Chênh lệch', compute='_compute_difference', store=True)
    
    reason = fields.Selection([
        ('overage', 'Hàng dư'),
        ('shortage', 'Hàng thiếu'),
        ('damage', 'Hàng lỗi')
    ], string='Lý do', required=True)
    
    solution_notes = fields.Text(string='Phương án giải quyết')
    
    warehouse_partner_id = fields.Many2one('res.partner', string='Bộ phận Kho tiếp nhận')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('mer.discrepancy.report') or _('New')
        return super(MerDiscrepancyReport, self).create(vals_list)

    @api.depends('expected_qty', 'actual_qty')
    def _compute_difference(self):
        for record in self:
            record.difference_qty = record.actual_qty - record.expected_qty

    def action_confirm_report(self):
        self.write({'state': 'reporting'})

    def action_start_solving(self):
        self.write({'state': 'solving'})
        
    def action_done(self):
        for report in self:
            if not report.warehouse_partner_id:
                raise UserError(_("Vui lòng chọn Bộ phận Kho tiếp nhận trước khi Hoàn tất để hệ thống gửi yêu cầu."))
                
            if report.reason == 'shortage':
                action_title = "YÊU CẦU BỔ SUNG HÀNG"
                action_body = "Sản phẩm đang bị Thiếu so với chứng từ. Vui lòng phía Kho kiểm tra lại quá trình giao nhận và tiến hành xuất Bổ sung hàng!"
            elif report.reason == 'overage':
                action_title = "YÊU CẦU THU HỒI HÀNG"
                action_body = "Phát hiện số lượng giao Thừa so với chứng từ. Yêu cầu bộ phận Kho tiến hành Thu hồi nhặt phần dư mang về Tổng kho!"
            else:  # damage
                action_title = "YÊU CẦU ĐỔI HÀNG"
                action_body = "Có hàng hóa giao đến bị Lỗi hỏng. Vui lòng phía Kho phối hợp thực hiện quy trình hoàn trả và xuất bồi hoàn Đổi hàng mới!"
                
            message = _(
                "[ %s ]\n"
                "Kính gửi bộ phận Kho!\n"
                "Phiếu sai lệch mã %s ghi nhận tình trạng sau:\n"
                "- Sản phẩm: %s\n"
                "- Chênh lệch: %s\n"
                "- Phương án giải quyết đề xuất: %s\n"
                "Chỉ đạo từ Merchandise: %s"
            ) % (
                action_title,
                report.name,
                report.product_id.name,
                abs(report.difference_qty),
                report.solution_notes or "Chưa có thêm ghi chú.",
                action_body
            )
            
            report.message_post(
                body=message,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
                partner_ids=[report.warehouse_partner_id.id]
            )
            
        self.write({'state': 'done'})
