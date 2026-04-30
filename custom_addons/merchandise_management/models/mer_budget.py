from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class MerPurchaseBudget(models.Model):
    _name = "mer.purchase.budget"
    _description = "Ngân sách mua hàng Merchandise"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, id desc"

    name = fields.Char(string="Tên ngân sách", required=True, tracking=True)
    date_from = fields.Date(string="Từ ngày", required=True, default=fields.Date.context_today)
    date_to = fields.Date(string="Đến ngày", required=True)
    category_id = fields.Many2one("product.category", string="Ngành hàng", required=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)
    budget_amount = fields.Monetary(string="Ngân sách", required=True, tracking=True)
    
    spent_amount = fields.Monetary(
        string="Đã sử dụng", 
        compute="_compute_spent_amount", 
        help="Tổng giá trị các PO đã duyệt trong khoảng thời gian này."
    )
    remaining_amount = fields.Monetary(string="Còn lại", compute="_compute_remaining_amount")
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('active', 'Đang áp dụng'),
        ('closed', 'Đã đóng')
    ], string="Trạng thái", default='draft', tracking=True)

    @api.depends('budget_amount', 'spent_amount')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.budget_amount - rec.spent_amount

    @api.depends('date_from', 'date_to', 'category_id')
    def _compute_spent_amount(self):
        for rec in self:
            # Tìm các PO liên kết với ngành hàng này trong khoảng thời gian
            pos = self.env['purchase.order'].search([
                ('state', 'in', ('purchase', 'done')),
                ('date_approve', '>=', rec.date_from),
                ('date_approve', '<=', rec.date_to),
            ])
            # Lọc các dòng PO thuộc ngành hàng này
            total = 0.0
            for po in pos:
                lines = po.order_line.filtered(lambda l: l.product_id.categ_id == rec.category_id)
                total += sum(lines.mapped('price_subtotal'))
            rec.spent_amount = total

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})
