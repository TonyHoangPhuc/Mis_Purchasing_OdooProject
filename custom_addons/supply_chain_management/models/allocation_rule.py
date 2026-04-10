from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SupplyChainAllocationRule(models.Model):
    _name = "supply.chain.allocation.rule"
    _description = "Quy tắc phân bổ chuỗi cung ứng"
    _order = "store_priority, partner_id, product_id"

    name = fields.Char(
        string="Tên quy tắc",
        compute="_compute_name",
        store=True,
    )
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cửa hàng",
        required=True,
        domain="[('sc_is_store', '=', True)]",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Kho",
        required=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Vị trí cửa hàng",
        required=True,
        domain="[('usage', '=', 'internal')]",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Sản phẩm",
        required=True,
    )
    store_priority = fields.Selection(
        related="partner_id.sc_store_priority",
        string="Mức ưu tiên cửa hàng",
        store=True,
        readonly=True,
    )
    min_qty = fields.Float(
        string="Tồn tối thiểu",
        digits="Product Unit of Measure",
        required=True,
        default=0.0,
    )
    max_qty = fields.Float(
        string="Tồn tối đa",
        digits="Product Unit of Measure",
        required=True,
        default=0.0,
    )
    current_qty = fields.Float(
        string="Tồn hiện có",
        compute="_compute_stock_metrics",
        digits="Product Unit of Measure",
    )
    replenishment_need_qty = fields.Float(
        string="Số lượng cần đề xuất",
        compute="_compute_stock_metrics",
        digits="Product Unit of Measure",
        search="_search_replenishment_need_qty",
    )
    company_id = fields.Many2one(
        "res.company",
        related="warehouse_id.company_id",
        string="Công ty",
        store=True,
        readonly=True,
    )

    @api.depends("partner_id", "product_id")
    def _compute_name(self):
        for rule in self:
            if rule.partner_id and rule.product_id:
                rule.name = f"{rule.partner_id.display_name} / {rule.product_id.display_name}"
            else:
                rule.name = False

    @api.depends("product_id", "location_id", "min_qty", "max_qty")
    def _compute_stock_metrics(self):
        Quant = self.env["stock.quant"].sudo()
        for rule in self:
            current_qty = 0.0
            if rule.product_id and rule.location_id:
                quants = Quant.search(
                    [
                        ("product_id", "=", rule.product_id.id),
                        ("location_id", "child_of", rule.location_id.id),
                    ]
                )
                current_qty = sum(quants.mapped("quantity"))
            need_qty = 0.0
            if current_qty < rule.min_qty:
                need_qty = max(rule.max_qty - current_qty, 0.0)
            rule.current_qty = current_qty
            rule.replenishment_need_qty = need_qty

    @api.constrains("min_qty", "max_qty")
    def _check_qty_limits(self):
        for rule in self:
            if rule.min_qty < 0 or rule.max_qty < 0:
                raise ValidationError("Tồn tối thiểu và tối đa phải lớn hơn hoặc bằng 0.")
            if rule.max_qty < rule.min_qty:
                raise ValidationError("Tồn tối đa phải lớn hơn hoặc bằng tồn tối thiểu.")

    def _search_replenishment_need_qty(self, operator, value):
        supported_operators = {">", ">=", "<", "<=", "=", "!="}
        if operator not in supported_operators:
            raise ValidationError("Toán tử tìm kiếm cho nhu cầu bổ sung hàng không được hỗ trợ.")

        rules = self.search([])
        matched_rules = rules.filtered(
            lambda rule: (
                (operator == ">" and rule.replenishment_need_qty > value)
                or (operator == ">=" and rule.replenishment_need_qty >= value)
                or (operator == "<" and rule.replenishment_need_qty < value)
                or (operator == "<=" and rule.replenishment_need_qty <= value)
                or (operator == "=" and rule.replenishment_need_qty == value)
                or (operator == "!=" and rule.replenishment_need_qty != value)
            )
        )
        return [("id", "in", matched_rules.ids)]
