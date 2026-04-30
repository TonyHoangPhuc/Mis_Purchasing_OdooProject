from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"



    def _search_is_due_soon(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            return []
        
        today = fields.Date.today()
        seven_days_later = today + datetime.timedelta(days=7)
        
        # Tìm các hóa đơn có hạn trong vòng 7 ngày tới và chưa thanh toán
        domain = [
            ('invoice_date_due', '>=', today),
            ('invoice_date_due', '<=', seven_days_later),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('state', '=', 'posted')
        ]
        
        # Nếu value là False, chúng ta đảo ngược logic (tuy nhiên thường bộ lọc chỉ dùng True)
        if (operator == "=" and not value) or (operator == "!=" and value):
            return [('id', 'not in', self.search(domain).ids)]
            
        return [('id', 'in', self.search(domain).ids)]

    is_due_soon = fields.Boolean(
        string="Sắp đến hạn",
        compute="_compute_nothing", # Không cần compute vì chỉ dùng để search
        search="_search_is_due_soon",
    )

    def _compute_nothing(self):
        for rec in self:
            rec.is_due_soon = False

    store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng",
        ondelete="restrict",
        index=True,
    )
