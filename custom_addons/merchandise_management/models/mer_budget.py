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
        string="Đã thực chi (PO)", 
        compute="_compute_amounts", 
        help="Tổng giá trị các PO đã duyệt trong khoảng thời gian này."
    )
    committed_amount = fields.Monetary(
        string="Đã cam kết (PR)",
        compute="_compute_amounts",
        help="Tổng giá trị các PR đã phê duyệt nhưng chưa chuyển thành PO."
    )
    remaining_amount = fields.Monetary(string="Còn lại thực tế", compute="_compute_amounts")
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('active', 'Đang áp dụng'),
        ('closed', 'Đã đóng')
    ], string="Trạng thái", default='draft', tracking=True)

    @api.depends('budget_amount', 'date_from', 'date_to', 'category_id')
    def _compute_amounts(self):
        for rec in self:
            # 1. Tính Spent Amount (Từ các PO đã xác nhận)
            pos = self.env['purchase.order'].search([
                ('state', 'in', ('purchase', 'done')),
                ('date_approve', '>=', rec.date_from),
                ('date_approve', '<=', rec.date_to),
            ])
            total_spent = 0.0
            for po in pos:
                lines = po.order_line.filtered(lambda l: l.product_id.categ_id == rec.category_id)
                total_spent += sum(lines.mapped('price_subtotal'))
            rec.spent_amount = total_spent

            # 2. Tính Committed Amount (Từ các PR đã duyệt nhưng chưa thành PO)
            prs = self.env['mer.purchase.request'].search([
                ('state', '=', 'approved'),
                ('date_request', '>=', rec.date_from),
                ('date_request', '<=', rec.date_to),
            ])
            total_committed = 0.0
            for pr in prs:
                lines = pr.line_ids.filtered(lambda l: l.product_id.categ_id == rec.category_id)
                total_committed += sum(lines.mapped('price_subtotal'))
            rec.committed_amount = total_committed

            # 3. Còn lại = Ngân sách - (Đã chi + Đã hứa chi)
            rec.remaining_amount = rec.budget_amount - (total_spent + total_committed)

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})
