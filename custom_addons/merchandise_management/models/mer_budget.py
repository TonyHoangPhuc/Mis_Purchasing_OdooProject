import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError


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
        store=True,
        tracking=True,
        help="Tổng giá trị các PO mới phát sinh sau mốc bắt đầu ghi nhận.",
    )
    committed_amount = fields.Monetary(
        string="Đã cam kết (PR)",
        compute="_compute_amounts",
        store=True,
        tracking=True,
        help="Tổng giá trị các PR mới phát sinh sau mốc bắt đầu ghi nhận.",
    )
    remaining_amount = fields.Monetary(
        string="Còn lại thực tế", 
        compute="_compute_amounts",
        store=True,
        tracking=True
    )

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

    def _get_budget_start_utc_naive(self):
        self.ensure_one()
        user_tz = self.env.user.tz or "Asia/Ho_Chi_Minh"
        tz = pytz.timezone(user_tz)
        local_start = tz.localize(fields.Datetime.to_datetime(self.date_from))
        return local_start.astimezone(pytz.utc).replace(tzinfo=None)

    @api.depends("budget_amount", "date_from", "date_to", "category_id", "usage_start_datetime", "state")
    def _compute_amounts(self):
        def _normalize_orm_datetime(value):
            if not value:
                return False

            dt_value = fields.Datetime.to_datetime(value)
            if dt_value.tzinfo:
                return dt_value.astimezone(pytz.utc).replace(tzinfo=None)

            return dt_value

        for budget in self:
            if not budget.category_id or not budget.date_from or not budget.date_to:
                budget.spent_amount = 0.0
                budget.committed_amount = 0.0
                budget.remaining_amount = budget.budget_amount or 0.0
                continue

            category_ids = self.env["product.category"].search(
                [("id", "child_of", budget.category_id.id)]
            ).ids
            # Chuyển đổi ngày sang giờ bắt đầu/kết thúc theo múi giờ người dùng
            user_tz = self.env.user.tz or 'Asia/Ho_Chi_Minh'
            from pytz import timezone, utc
            tz = timezone(user_tz)
            
            # Odoo Datetime trong ORM/search là UTC naive, nên chuẩn hóa hết về cùng kiểu này
            dt_from = tz.localize(
                fields.Datetime.to_datetime(budget.date_from)
            ).astimezone(utc).replace(tzinfo=None)
            dt_to = tz.localize(
                fields.Datetime.to_datetime(budget.date_to).replace(hour=23, minute=59, second=59)
            ).astimezone(utc).replace(tzinfo=None)

            usage_start = (
                _normalize_orm_datetime(budget.usage_start_datetime)
                or _normalize_orm_datetime(budget.create_date)
                or dt_from
            )
            date_from = max(dt_from, usage_start)
            date_to = dt_to

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
            budget.remaining_amount = budget.budget_amount - total_spent

    def action_activate(self):
        for budget in self:
            missing_fields = []
            if not budget.name:
                missing_fields.append("Tên ngân sách")
            if not budget.category_id:
                missing_fields.append("Ngành hàng")
            if not budget.date_from:
                missing_fields.append("Từ ngày")
            if not budget.date_to:
                missing_fields.append("Đến ngày")
            if budget.budget_amount <= 0:
                missing_fields.append("Ngân sách phải lớn hơn 0")

            if missing_fields:
                raise UserError(
                    "Chưa thể kích hoạt ngân sách. Vui lòng bổ sung:\n- %s"
                    % "\n- ".join(missing_fields)
                )

            if budget.date_from > budget.date_to:
                raise UserError("Chưa thể kích hoạt ngân sách. 'Từ ngày' không được lớn hơn 'Đến ngày'.")

            vals = {"state": "active"}
            if not budget.usage_start_datetime:
                vals["usage_start_datetime"] = budget._get_budget_start_utc_naive()
            budget.write(vals)

    def action_close(self):
        self.write({"state": "closed"})
