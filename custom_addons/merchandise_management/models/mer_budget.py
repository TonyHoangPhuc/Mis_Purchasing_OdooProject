from datetime import timedelta

from odoo import api, fields, models


class MerPurchaseBudget(models.Model):
    _name = "mer.purchase.budget"
    _description = "Ngân sách mua hàng Merchandise"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, id desc"

    name = fields.Char(string="Tên ngân sách", required=True, tracking=True)
    date_from = fields.Date(
        string="Từ ngày",
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    date_to = fields.Date(string="Đến ngày", required=True)
    usage_start_datetime = fields.Datetime(
        string="Bắt đầu ghi nhận",
        readonly=True,
        copy=False,
        help=(
            "Mốc bắt đầu tính đã thực chi/cam kết cho ngân sách này. "
            "PO/PR cũ trước mốc này không bị trừ vào ngân sách mới."
        ),
    )
    category_id = fields.Many2one("product.category", string="Ngành hàng", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        default=lambda self: self.env.company.currency_id,
    )
    budget_amount = fields.Monetary(string="Ngân sách", required=True, tracking=True)

    spent_amount = fields.Monetary(
        string="Đã thực chi (PO)",
        compute="_compute_amounts",
        help="Tổng giá trị các PO mới phát sinh sau mốc bắt đầu ghi nhận.",
    )
    committed_amount = fields.Monetary(
        string="Đã cam kết (PR)",
        compute="_compute_amounts",
        help="Tổng giá trị các PR mới phát sinh sau mốc bắt đầu ghi nhận.",
    )
    remaining_amount = fields.Monetary(string="Còn lại thực tế", compute="_compute_amounts")

    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("active", "Đang áp dụng"),
            ("closed", "Đã đóng"),
        ],
        string="Trạng thái",
        default="draft",
        tracking=True,
    )

    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute(
            """
            UPDATE mer_purchase_budget
               SET usage_start_datetime = create_date
             WHERE usage_start_datetime IS NULL
               AND state = 'active'
            """
        )
        return res

    @api.depends("budget_amount", "date_from", "date_to", "category_id", "usage_start_datetime")
    def _compute_amounts(self):
        for budget in self:
            if not budget.category_id or not budget.date_from or not budget.date_to:
                budget.spent_amount = 0.0
                budget.committed_amount = 0.0
                budget.remaining_amount = budget.budget_amount or 0.0
                continue

            category_ids = self.env["product.category"].search(
                [("id", "child_of", budget.category_id.id)]
            ).ids
            period_start = fields.Datetime.to_datetime(budget.date_from)
            usage_start = budget.usage_start_datetime or budget.create_date or period_start
            date_from = max(period_start, usage_start)
            date_to = fields.Datetime.to_datetime(budget.date_to + timedelta(days=1))

            purchase_orders = self.env["purchase.order"].search(
                [
                    ("state", "in", ("purchase", "done")),
                    ("date_approve", ">=", date_from),
                    ("date_approve", "<", date_to),
                ]
            )
            total_spent = 0.0
            for order in purchase_orders:
                lines = order.order_line.filtered(
                    lambda line: line.product_id.categ_id.id in category_ids
                )
                total_spent += sum(lines.mapped("price_subtotal"))
            budget.spent_amount = total_spent

            requests = self.env["mer.purchase.request"].search(
                [
                    ("state", "=", "approved"),
                    ("date_request", ">=", budget.date_from),
                    ("date_request", "<=", budget.date_to),
                    ("create_date", ">=", date_from),
                ]
            )
            total_committed = 0.0
            for request in requests:
                lines = request.line_ids.filtered(
                    lambda line: line.product_id.categ_id.id in category_ids
                )
                total_committed += sum(lines.mapped("price_subtotal"))
            budget.committed_amount = total_committed
            budget.remaining_amount = budget.budget_amount - (total_spent + total_committed)

    def action_activate(self):
        for budget in self:
            vals = {"state": "active"}
            if not budget.usage_start_datetime:
                vals["usage_start_datetime"] = fields.Datetime.now()
            budget.write(vals)

    def action_close(self):
        self.write({"state": "closed"})
