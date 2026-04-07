from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MerPurchaseRequestLine(models.Model):
    _name = 'mer.purchase.request.line'
    _description = 'Chi tiết sản phẩm yêu cầu mua hàng'

    request_id = fields.Many2one('mer.purchase.request', string='Yêu cầu')
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    product_qty = fields.Float(string='Số lượng', default=1.0)
    product_uom_id = fields.Many2one('uom.uom', string='Đơn vị tính', related='product_id.uom_id')

class MerPurchaseRequest(models.Model):
    _name = 'mer.purchase.request'
    _description = 'Yêu cầu mua hàng Merchandise'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã yêu cầu', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Đã gửi (Chờ xử lý)'),
        ('to_approve', 'Chờ Quản lý duyệt'),
        ('approved', 'Được phê duyệt'),
        ('po_created', 'Đã tạo PO'),
        ('rejected', 'Từ chối'),
        ('cancel', 'Hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    user_id = fields.Many2one('res.users', string='Người tạo', default=lambda self: self.env.user, tracking=True)
    manager_id = fields.Many2one('res.users', string='Người phê duyệt', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Kho cung cấp', required=True)
    date_request = fields.Date(string='Ngày yêu cầu', default=fields.Date.today)
    
    line_ids = fields.One2many('mer.purchase.request.line', 'request_id', string='Chi tiết sản phẩm')
    
    purchase_id = fields.Many2one('purchase.order', string='Đơn mua hàng (PO)', readonly=True)
    notes = fields.Text(string='Ghi chú')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('mer.purchase.request') or _('New')
        return super(MerPurchaseRequest, self).create(vals_list)

    def action_submit(self):
        for request in self:
            if not request.line_ids:
                raise UserError(_("Bạn không thể gửi yêu cầu khi chưa chọn sản phẩm nào!"))
        self.write({'state': 'submitted'})

    def action_send_to_manager(self):
        self.write({'state': 'to_approve'})

    def action_approve(self):
        self.write({'state': 'approved', 'manager_id': self.env.user.id})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_create_po(self):
        if self.state != 'approved':
            raise UserError(_("Yêu cầu cần được phê duyệt trước khi tạo PO."))
        
        if not self.partner_id:
            raise UserError(_("Vui lòng chọn Nhà cung cấp trước khi tạo PO."))

        purchase_vals = {
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'date_order': fields.Datetime.now(),
            'order_line': [],
        }
        
        for line in self.line_ids:
            if line.product_id.x_mer_stop_ordering:
                raise UserError(_("Sản phẩm %s đang trong trạng thái dừng đặt hàng.") % line.product_id.name)
                
            purchase_vals['order_line'].append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_qty': line.product_qty,
                'product_uom_id': line.product_uom_id.id,
                'price_unit': line.product_id.standard_price,
                'date_planned': fields.Datetime.now(),
            }))
            
        purchase_id = self.env['purchase.order'].create(purchase_vals)
        # Tự động Xác nhận đơn hàng (Confirm Order) luôn
        purchase_id.button_confirm()
        
        self.write({'purchase_id': purchase_id.id, 'state': 'po_created'})

        # Gửi thông báo cho Kho về đơn PO vừa được tạo
        if self.partner_id:
            message_body = _(
                "THÔNG BÁO ĐƠN MUA HÀNG (PO)\n"
                "Chào %s, hệ thống ghi nhận một đơn mua hàng mới từ Merchandise:\n"
                "- Mã PO: %s\n"
                "- Nhà cung cấp: %s\n"
                "Vui lòng tiếp nhận thông tin đơn hàng này!"
            ) % (
                self.partner_id.name,
                purchase_id.name, 
                self.partner_id.name
            )
            
            # Đưa Kho vào danh sách theo dõi và bắn tin nhắn
            self.message_subscribe(partner_ids=[self.partner_id.id])
            self.message_post(
                body=message_body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                partner_ids=[self.partner_id.id]
            )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': purchase_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
