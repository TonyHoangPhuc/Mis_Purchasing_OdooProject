from odoo import api, fields, models, _


class StoreVendorBill(models.Model):
    _name = "store.vendor.bill"
    _description = "Hóa đơn Nhà cung cấp đơn giản"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Số hóa đơn",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Mới"),
    )
    purchase_id = fields.Many2one(
        "purchase.order",
        string="Đơn PO",
        required=True,
        index=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        related="purchase_id.partner_id",
        store=True,
        readonly=True,
    )
    mer_request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yêu cầu Merchandise",
        related="purchase_id.mer_request_id",
        store=True,
        readonly=True,
    )
    store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng",
        related="mer_request_id.store_id",
        store=True,
        readonly=True,
    )
    invoice_origin = fields.Char(string="Chứng từ gốc", readonly=True)
    date_bill = fields.Date(
        string="Ngày hóa đơn",
        default=lambda self: fields.Date.context_today(self),
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("confirmed", "Đã xác nhận"),
            ("cancel", "Đã hủy"),
        ],
        string="Trạng thái",
        default="draft",
        tracking=True,
    )
    line_ids = fields.One2many(
        "store.vendor.bill.line",
        "bill_id",
        string="Chi tiết hóa đơn",
    )
    amount_total = fields.Float(
        string="Tổng tiền",
        compute="_compute_amount_total",
        store=True,
    )
    notes = fields.Text(string="Ghi chú")

    _sql_constraints = [
        (
            "unique_purchase_bill",
            "unique(purchase_id)",
            "PO này đã có hóa đơn Nhà cung cấp.",
        )
    ]

    @api.depends("line_ids.price_subtotal")
    def _compute_amount_total(self):
        for bill in self:
            bill.amount_total = sum(bill.line_ids.mapped("price_subtotal"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Mới")) == _("Mới"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("store.vendor.bill")
                    or _("Mới")
                )
        return super().create(vals_list)

    def action_confirm(self):
        self.write({"state": "confirmed"})
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        return True

    @api.model
    def _create_from_purchase_orders(self, purchase_orders, notes=False):
        bills = self.env["store.vendor.bill"]
        for po in purchase_orders:
            if po.state not in ("purchase", "done"):
                continue
            existing_bill = self.search([("purchase_id", "=", po.id)], limit=1)
            if existing_bill:
                bills |= existing_bill
                continue

            bill_lines = []
            for line in po.order_line.filtered(lambda current: not current.display_type):
                quantity = line.qty_received or line.product_qty
                if quantity <= 0:
                    continue
                bill_lines.append(
                    (
                        0,
                        0,
                        {
                            "product_id": line.product_id.id,
                            "name": line.name or line.product_id.display_name,
                            "quantity": quantity,
                            "product_uom_id": line.product_uom_id.id,
                            "price_unit": line.price_unit,
                        },
                    )
                )

            if not bill_lines:
                continue

            bills |= self.create(
                {
                    "purchase_id": po.id,
                    "invoice_origin": po.name,
                    "notes": notes or _("Tự động tạo sau khi hoàn tất nhận hàng."),
                    "line_ids": bill_lines,
                }
            )
        return bills


class StoreVendorBillLine(models.Model):
    _name = "store.vendor.bill.line"
    _description = "Dòng hóa đơn Nhà cung cấp đơn giản"

    bill_id = fields.Many2one(
        "store.vendor.bill",
        string="Hóa đơn",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one("product.product", string="Sản phẩm")
    name = fields.Char(string="Mô tả", required=True)
    quantity = fields.Float(string="Số lượng", required=True, default=1.0)
    product_uom_id = fields.Many2one("uom.uom", string="Đơn vị")
    price_unit = fields.Float(string="Đơn giá")
    price_subtotal = fields.Float(
        string="Thành tiền",
        compute="_compute_price_subtotal",
        store=True,
    )

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
