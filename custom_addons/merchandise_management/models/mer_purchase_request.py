import operator as py_operator

from odoo import _, api, fields, models
from odoo.exceptions import UserError


COUNT_COMPARISON_OPERATORS = {
    "=": py_operator.eq,
    "!=": py_operator.ne,
    ">": py_operator.gt,
    ">=": py_operator.ge,
    "<": py_operator.lt,
    "<=": py_operator.le,
}

class MerPurchaseRequestLine(models.Model):
    _name = 'mer.purchase.request.line'
    _description = 'Chi tiết sản phẩm yêu cầu mua hàng'
    # Lưu trữ danh sách sản phẩm cần mua

    request_id = fields.Many2one('mer.purchase.request', string='Yêu cầu')
    product_id = fields.Many2one('product.product', string='Sản phẩm', required=True)
    product_qty = fields.Float(string='Số lượng', default=1.0)
    product_uom_id = fields.Many2one('uom.uom', string='Đơn vị tính', related='product_id.uom_id')

# Quy trình phê duyệt yêu cầu mua hàng (PR)
class MerPurchaseRequest(models.Model):
    _name = 'mer.purchase.request'
    _description = 'Yêu cầu mua hàng Merchandise'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã yêu cầu', required=True, copy=False, readonly=True, index=True, default=lambda self: _('Mới'))
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Đã gửi (Chờ xử lý)'),
        ('to_approve', 'Chờ Quản lý duyệt'),
        ('approved', 'Được phê duyệt'),
        ('po_created', 'Đã tạo PO'),
        ('done', 'Hoàn tất'),
        ('rejected', 'Từ chối'),
        ('cancel', 'Hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    user_id = fields.Many2one('res.users', string='Người tạo', default=lambda self: self.env.user, tracking=True)
    manager_id = fields.Many2one('res.users', string='Người phê duyệt', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Kho tổng / Nhà cung cấp', required=True)
    company_partner_id = fields.Many2one('res.partner', compute='_compute_company_partner_id', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Cửa hàng', required=True, default=lambda self: self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1))
    date_request = fields.Date(string='Ngày yêu cầu', default=fields.Date.today)
    
    line_ids = fields.One2many('mer.purchase.request.line', 'request_id', string='Chi tiết sản phẩm')
    
    purchase_order_count = fields.Integer(
        string='Số PO',
        compute='_compute_purchase_order_count',
        search='_search_purchase_order_count',
    )

    @api.model
    def _get_purchase_order_count_map(self):
        grouped_data = self.env['purchase.order'].sudo().read_group(
            [('origin', '!=', False)],
            ['origin'],
            ['origin'],
            lazy=False,
        )
        return {
            data['origin']: data.get('origin_count', data.get('__count', 0))
            for data in grouped_data
            if data.get('origin')
        }

    def _compute_purchase_order_count(self):
        count_map = self._get_purchase_order_count_map()
        for req in self:
            req.purchase_order_count = count_map.get(req.name, 0)

    @api.model
    def _search_purchase_order_count(self, operator, value):
        comparator = COUNT_COMPARISON_OPERATORS.get(operator)
        if comparator is None:
            raise UserError(_("Toán tử %s không được hỗ trợ cho bộ lọc số PO.") % operator)

        try:
            target_value = int(value)
        except (TypeError, ValueError) as exc:
            raise UserError(_("Giá trị lọc số PO không hợp lệ: %s") % value) from exc

        count_map = self._get_purchase_order_count_map()
        matching_ids = [
            request.id
            for request in self.search([])
            if comparator(count_map.get(request.name, 0), target_value)
        ]
        return [('id', 'in', matching_ids)]

    def action_view_purchase_orders(self):
        self.ensure_one()
        po_ids = self.env['purchase.order'].sudo().search([('origin', '=', self.name)]).ids
        return {
            'name': _('Các Đơn mua hàng (PO)'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', po_ids)],
            'target': 'current',
        }
    notes = fields.Text(string='Ghi chú')

    # Sinh mã PR theo sequence khi tạo mới
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) in (_('Mới'), _('New')):
                vals['name'] = self.env['ir.sequence'].next_by_code('mer.purchase.request') or _('Mới')
        return super(MerPurchaseRequest, self).create(vals_list)

    @api.depends('warehouse_id')
    def _compute_company_partner_id(self):
        for request in self:
            company = request.warehouse_id.company_id or self.env.company
            request.company_partner_id = company.partner_id

    def _get_tagged_supplier_partners(self, product):
        supplier_category = self.env['res.partner.category'].search([('name', '=', 'NCC')], limit=1)
        partners = product.seller_ids.mapped('partner_id')
        if supplier_category:
            return partners.filtered(lambda partner: supplier_category in partner.category_id)
        return self.env['res.partner']

    # Gợi ý NCC/Kho tổng dựa trên sản phẩm đầu tiên
    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        domain = []
        if self.line_ids:
            first_product = self.line_ids[0].product_id
            if first_product and first_product.x_mer_supply_route == 'supplier_direct':
                domain = [('category_id.name', '=', 'NCC')]
                suppliers = self._get_tagged_supplier_partners(first_product)
                if not self.partner_id or self.partner_id not in suppliers:
                    self.partner_id = suppliers[:1].id or False
            else:
                company_partner = self.company_partner_id or self.env.company.partner_id
                domain = [('id', '=', company_partner.id)] if company_partner else []
                self.partner_id = company_partner
        return {'domain': {'partner_id': domain}}

    # Gửi yêu cầu mua hàng
    def action_submit(self):
        for request in self:
            if not request.line_ids:
                raise UserError(_("Bạn không thể gửi yêu cầu khi chưa chọn sản phẩm nào!"))
        self.write({'state': 'submitted'})

    # Gửi lên Quản lý duyệt
    def action_send_to_manager(self):
        self.write({'state': 'to_approve'})

    # Phê duyệt yêu cầu
    def action_approve(self):
        self.write({'state': 'approved', 'manager_id': self.env.user.id})

    # Từ chối yêu cầu
    def action_reject(self):
        self.write({'state': 'rejected'})

    # Đưa về bản nháp
    def action_draft(self):
        self.write({'state': 'draft'})

    # Hủy yêu cầu
    def action_cancel(self):
        self.write({'state': 'cancel'})

    # Hoàn tất yêu cầu
    def action_done(self):
        self.write({'state': 'done'})

    # Tạo PO từ yêu cầu đã duyệt
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
            
        purchase_id = self.env['purchase.order'].sudo().create(purchase_vals)
        # Tự động xác nhận đơn hàng (Confirm Order)
        purchase_id.button_confirm()
        
        self.write({'state': 'done'})

        # Gửi thông báo Chatter cho bộ phận Kho
        if self.partner_id:
            from markupsafe import Markup
            
            message_body = Markup(
                "<div style='background-color: #f0fdf4; border-left: 5px solid #22c55e; padding: 15px; border-radius: 4px; font-family: sans-serif;'>"
                    "<h3 style='margin-top: 0; color: #166534; border-bottom: 1px solid #bbf7d0; padding-bottom: 8px;'>📦 %s</h3>"
                    "<p style='color: #15803d; margin: 10px 0;'>"
                        "Chào bộ phận Kho, hệ thống ghi nhận một đơn mua hàng mới từ Merchandise:"
                    "</p>"
                    "<ul style='list-style: none; padding: 0; margin: 10px 0; color: #15803d; line-height: 1.6;'>"
                        "<li><b>🔢 %s:</b> %s</li>"
                        "<li><b>🏢 %s:</b> %s</li>"
                    "</ul>"
                    "<p style='margin-bottom: 0; font-style: italic; color: #166534; font-size: 0.9em; border-top: 1px dashed #bbf7d0; padding-top: 8px;'>"
                        "💡 <i>Vui lòng chuẩn bị hàng và lên kế hoạch giao cho Cửa hàng sớm nhất!</i>"
                    "</p>"
                "</div>"
            ) % (
                _("THÔNG BÁO ĐƠN MUA HÀNG (PO) MỚI"),
                _("Mã PO"), purchase_id.name,
                _("Nhà cung cấp"), self.partner_id.name,
            )
            
            # Gửi tin nhắn thông báo cho Kho
            self.message_subscribe(partner_ids=[self.partner_id.id])
            self.message_post(
                body=message_body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                partner_ids=[self.partner_id.id]
            )
        return self.action_view_purchase_orders()
