import datetime
from collections import defaultdict

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StoreStore(models.Model):
    _name = "store.store"
    _description = "Cửa hàng"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Tên cửa hàng", required=True, tracking=True)
    code = fields.Char(string="Mã cửa hàng", required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Người phụ trách",
        default=lambda self: self.env.user,
        tracking=True,
    )
    store_priority = fields.Selection(
        [
            ("high", "Cao"),
            ("medium", "Trung bình"),
            ("low", "Thấp"),
        ],
        string="Mức ưu tiên bổ sung",
        default="medium",
        required=True,
        tracking=True,
    )
    phone = fields.Char(string="Điện thoại")
    email = fields.Char(string="Email")
    street = fields.Char(string="Địa chỉ")
    street2 = fields.Char(string="Địa chỉ 2")
    city = fields.Char(string="Thành phố")
    zip = fields.Char(string="Mã bưu điện")
    state_id = fields.Many2one("res.country.state", string="Tỉnh/Thành")
    country_id = fields.Many2one("res.country", string="Quốc gia")
    note = fields.Text(string="Ghi chú")
    partner_id = fields.Many2one(
        "res.partner",
        string="Đối tác cửa hàng",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Kho cửa hàng",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    product_line_ids = fields.One2many(
        "store.product.line",
        "store_id",
        string="Danh mục sản phẩm",
    )
    product_count = fields.Integer(
        string="Số mặt hàng",
        compute="_compute_counts",
    )
    replenishment_count = fields.Integer(
        string="Mặt hàng cần bổ sung",
        compute="_compute_counts",
    )
    purchase_request_count = fields.Integer(
        string="Số PR",
        compute="_compute_counts",
    )
    sales_order_count = fields.Integer(
        string="Số đơn bán",
        compute="_compute_counts",
    )
    needs_replenishment = fields.Boolean(
        string="Cần bổ sung hàng",
        compute="_compute_counts",
        search="_search_needs_replenishment",
    )
    total_internal_cost = fields.Monetary(
        string="Tổng chi phí điều chuyển",
        compute="_compute_financial_metrics",
        currency_field="currency_id",
        store=True,
    )
    total_sales_revenue = fields.Monetary(
        string="Tổng doanh thu cửa hàng",
        compute="_compute_financial_metrics",
        currency_field="currency_id",
        store=True,
    )
    gross_profit = fields.Monetary(
        string="Lợi nhuận gộp",
        compute="_compute_financial_metrics",
        currency_field="currency_id",
        store=True,
    )
    profit_margin = fields.Float(
        string="Tỷ suất lợi nhuận (%)",
        compute="_compute_financial_metrics",
        store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        related="company_id.currency_id",
        readonly=True,
    )

    _sql_constraints = [
        ("store_code_company_uniq", "unique(code, company_id)", "Mã cửa hàng phải là duy nhất theo công ty."),
        ("store_partner_uniq", "unique(partner_id)", "Mỗi cửa hàng chỉ được liên kết với một đối tác."),
        ("store_warehouse_uniq", "unique(warehouse_id)", "Mỗi cửa hàng chỉ được liên kết với một kho."),
    ]

    @api.constrains("code")
    def _check_code(self):
        for store in self:
            if not store.code:
                continue
            normalized = store._normalize_store_code(store.code)
            if normalized != store.code:
                raise ValidationError("Mã cửa hàng chỉ gồm chữ/số in hoa và tối đa 5 ký tự.")

    @api.depends("product_line_ids", "product_line_ids.suggested_replenishment_qty")
    def _compute_counts(self):
        sale_order_count_map = {}
        purchase_request_count_map = {}
        if self.ids:
            sale_order_data = self.env["sale.order"].read_group(
                [("store_id", "in", self.ids)],
                ["store_id"],
                ["store_id"],
            )
            pr_data = self.env["mer.purchase.request"].read_group(
                [("store_id", "in", self.ids)],
                ["store_id"],
                ["store_id"],
            )
            sale_order_count_map = {
                item["store_id"][0]: item["store_id_count"]
                for item in sale_order_data
                if item.get("store_id")
            }
            purchase_request_count_map = {
                item["store_id"][0]: item["store_id_count"]
                for item in pr_data
                if item.get("store_id")
            }

        for store in self:
            store.product_count = len(store.product_line_ids)
            store.replenishment_count = len(store.product_line_ids.filtered("needs_replenishment"))
            store.needs_replenishment = bool(store.replenishment_count)
            store.purchase_request_count = purchase_request_count_map.get(store.id, 0)
            store.sales_order_count = sale_order_count_map.get(store.id, 0)

    def _compute_financial_metrics(self):
        for store in self:
            # Bỏ quyết toán nội bộ theo yêu cầu
            total_cost = 0.0
            
            # 2. Tính doanh thu từ Sale Orders
            sales = self.env["sale.order"].search([
                ("store_id", "=", store.id),
                ("state", "in", ("sale", "done")),
            ])
            total_revenue = sum(sales.mapped("amount_untaxed"))
            
            # 3. Tính Lợi nhuận
            profit = total_revenue - total_cost
            margin = (profit / total_revenue * 100) if total_revenue else 0.0
            
            store.total_internal_cost = total_cost
            store.total_sales_revenue = total_revenue
            store.gross_profit = profit
            store.profit_margin = margin

    def _search_needs_replenishment(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise ValidationError("Chỉ hỗ trợ tìm kiếm Có/Không cho cờ cần bổ sung hàng.")

        matched_ids = self.search([]).filtered(lambda store: store.replenishment_count > 0).ids
        domain = [("id", "in", matched_ids)]
        return domain if (operator == "=" and value) or (operator == "!=" and not value) else [("id", "not in", matched_ids)]

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            vals["code"] = self._normalize_store_code(vals.get("code") or vals.get("name"))
            company_id = vals.get("company_id") or self.env.company.id
            partner = self.env["res.partner"].create(self._prepare_partner_vals(vals))
            warehouse = self.env["stock.warehouse"].create(
                self._prepare_warehouse_vals(vals, company_id, partner.id)
            )
            vals["partner_id"] = partner.id
            vals["warehouse_id"] = warehouse.id
            new_vals_list.append(vals)

        stores = super().create(new_vals_list)

        for store in stores:
            store.warehouse_id.write({"store_record_id": store.id})
            if "sc_is_store" in store.partner_id._fields:
                store.partner_id.write(
                    {
                        "sc_is_store": True,
                        "sc_store_priority": store.store_priority,
                    }
                )
        return stores

    def write(self, vals):
        vals = dict(vals)
        if vals.get("code"):
            vals["code"] = self._normalize_store_code(vals["code"])

        partner_fields = {}
        if "name" in vals:
            partner_fields["name"] = vals["name"]
        for field_name in ("phone", "email", "street", "street2", "city", "zip", "state_id", "country_id", "active"):
            if field_name in vals:
                partner_fields[field_name] = vals[field_name]

        warehouse_fields = {}
        if "name" in vals:
            warehouse_fields["name"] = vals["name"]
        if "code" in vals:
            warehouse_fields["code"] = vals["code"]
        if "company_id" in vals:
            warehouse_fields["company_id"] = vals["company_id"]
        if "active" in vals:
            warehouse_fields["active"] = vals["active"]

        result = super().write(vals)

        for store in self:
            if partner_fields:
                store.partner_id.write(partner_fields)
            if "store_priority" in vals and "sc_store_priority" in store.partner_id._fields:
                store.partner_id.write({"sc_store_priority": store.store_priority})
            if warehouse_fields:
                warehouse_update = dict(warehouse_fields)
                warehouse_update["mis_role"] = "store"
                store.warehouse_id.write(warehouse_update)
        return result

    def unlink(self):
        for store in self:
            if self.env["mer.purchase.request"].search_count([("store_id", "=", store.id)]):
                raise UserError(
                    _("Không thể xóa cửa hàng đã có yêu cầu mua hàng. Hãy lưu trữ cửa hàng thay vì xóa.")
                )
        return super().unlink()

    @api.model
    def _normalize_store_code(self, raw_code):
        raw_code = (raw_code or "").upper()
        normalized = "".join(char for char in raw_code if char.isalnum())[:5]
        if not normalized:
            raise ValidationError("Mã cửa hàng là bắt buộc và chỉ gồm chữ/số.")
        return normalized

    @api.model
    def _prepare_partner_vals(self, vals):
        return {
            "name": vals.get("name"),
            "phone": vals.get("phone"),
            "email": vals.get("email"),
            "street": vals.get("street"),
            "street2": vals.get("street2"),
            "city": vals.get("city"),
            "zip": vals.get("zip"),
            "state_id": vals.get("state_id"),
            "country_id": vals.get("country_id"),
            "company_id": vals.get("company_id") or self.env.company.id,
            "type": "delivery",
        }

    @api.model
    def _prepare_warehouse_vals(self, vals, company_id, partner_id):
        return {
            "name": vals.get("name"),
            "code": vals.get("code"),
            "company_id": company_id,
            "partner_id": partner_id,
            "mis_role": "store",
            "reception_steps": "one_step",
            "delivery_steps": "ship_only",
        }

    def _get_central_warehouse(self):
        self.ensure_one()
        warehouse = self.env["stock.warehouse"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("mis_role", "=", "central"),
            ],
            limit=1,
        )
        if warehouse:
            return warehouse
        return self.env["stock.warehouse"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("id", "!=", self.warehouse_id.id),
                ("store_record_id", "=", False),
            ],
            limit=1,
        )

    def action_relink_warehouse(self):
        """Khắc phục các cửa hàng bị liên kết nhầm với kho tổng hoặc kho không đúng mã."""
        for store in self:
            code = store.code or store._normalize_store_code(store.name)
            warehouse = self.env["stock.warehouse"].search([("code", "=", code)], limit=1)
            if warehouse and warehouse != store.warehouse_id:
                store.write({"warehouse_id": warehouse.id})
                warehouse.write({"store_record_id": store.id, "mis_role": "store"})
            elif not warehouse:
                # Nếu không tìm thấy kho theo mã, tạo mới kho chuẩn cho cửa hàng
                warehouse = self.env["stock.warehouse"].create(
                    self._prepare_warehouse_vals({"name": store.name, "code": code}, store.company_id.id, store.partner_id.id)
                )
                store.write({"warehouse_id": warehouse.id})
                warehouse.write({"store_record_id": store.id})
        return True

    def _get_replenishment_lines(self):
        self.ensure_one()
        return self.product_line_ids.filtered(lambda line: line.suggested_replenishment_qty > 0 and line.active)

    def action_view_product_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("store_management.action_store_product_lines")
        action["domain"] = [("store_id", "=", self.id)]
        action["context"] = {"default_store_id": self.id}
        return action

    def action_view_purchase_requests(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("store_management.action_store_purchase_requests")
        action["domain"] = [("store_id", "=", self.id)]
        action["context"] = {
            "default_store_id": self.id,
            "from_store_menu": 1,
        }
        return action

    def action_view_sales_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("store_management.action_store_sales_orders")
        action["domain"] = [("store_id", "=", self.id)]
        action["context"] = {"default_store_id": self.id}
        return action

    def action_view_receipts(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("store_management.action_store_receipts")
        action["domain"] = [
            "|",
            "&",
            ("picking_type_code", "=", "incoming"),
            ("picking_type_id.warehouse_id", "=", self.warehouse_id.id),
            "&",
            ("picking_type_code", "=", "internal"),
            ("location_dest_id.warehouse_id", "=", self.warehouse_id.id),
        ]
        action["context"] = {"default_picking_type_id": self.warehouse_id.in_type_id.id}
        return action

    def action_create_replenishment_pr(self):
        self.ensure_one()
        lines = self._get_replenishment_lines()
        if not lines:
            raise UserError(_("Cửa hàng này hiện chưa có mặt hàng nào cần bổ sung hàng."))

        duplicate_request = self.env["mer.purchase.request"]._find_duplicate_store_request(
            self.id,
            lines.mapped("product_id").ids,
        )
        if duplicate_request:
            raise UserError(
                _(
                    "Đã tồn tại PR %(pr)s đang xử lý cho các mặt hàng bổ sung của cửa hàng này. "
                    "Không thể tạo PR mới trùng mặt hàng."
                )
                % {"pr": duplicate_request.name}
            )

        central_warehouse = self._get_central_warehouse()
        if not central_warehouse:
            raise UserError(_("Chưa cấu hình Kho tổng để Merchandise xử lý yêu cầu của cửa hàng."))

        request = self.env["mer.purchase.request"].create(
            {
                "store_id": self.id,
                "warehouse_id": self.warehouse_id.id,
                "notes": _("PR được tạo tự động từ định mức tồn kho của cửa hàng."),
                "line_ids": [
                    Command.create(
                        {
                            "product_id": line.product_id.id,
                            "product_qty": line.suggested_replenishment_qty,
                        }
                    )
                    for line in lines
                ],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "mer.purchase.request",
            "res_id": request.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": {
                "from_store_menu": 1,
                "default_store_id": self.id,
            },
        }


class StoreProductLine(models.Model):
    _name = "store.product.line"
    _description = "Định mức sản phẩm theo cửa hàng"
    _order = "store_id, product_id"

    store_id = fields.Many2one(
        "store.store",
        string="Cửa hàng",
        required=True,
        ondelete="cascade",
    )
    active = fields.Boolean(default=True)
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Kho cửa hàng",
        related="store_id.warehouse_id",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Đối tác cửa hàng",
        related="store_id.partner_id",
        store=True,
        readonly=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Vị trí tồn",
        related="store_id.warehouse_id.lot_stock_id",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Sản phẩm",
        required=True,
    )
    categ_id = fields.Many2one(
        "product.category",
        string="Ngành hàng",
        related="product_id.categ_id",
        store=True,
        readonly=True,
    )
    min_qty = fields.Float(
        string="Tồn tối thiểu",
        digits="Product Unit of Measure",
        default=0.0,
        required=True,
    )
    max_qty = fields.Float(
        string="Tồn tối đa",
        digits="Product Unit of Measure",
        default=0.0,
        required=True,
    )
    current_qty = fields.Float(
        string="Tồn hiện có",
        digits="Product Unit of Measure",
        compute="_compute_stock_metrics",
    )
    available_qty = fields.Float(
        string="Khả dụng",
        digits="Product Unit of Measure",
        compute="_compute_stock_metrics",
    )
    pending_replenishment_qty = fields.Float(
        string="Đang chờ bổ sung",
        digits="Product Unit of Measure",
        compute="_compute_stock_metrics",
    )
    suggested_replenishment_qty = fields.Float(
        string="Đề xuất bổ sung",
        digits="Product Unit of Measure",
        compute="_compute_stock_metrics",
    )
    sales_velocity_30d = fields.Float(
        string="Tốc độ bán (30n)",
        digits="Product Unit of Measure",
        compute="_compute_stock_metrics",
        help="Số lượng bán trung bình mỗi ngày trong 30 ngày qua.",
    )
    days_of_stock = fields.Float(
        string="Ngày tồn dự kiến",
        compute="_compute_stock_metrics",
        help="Số ngày dự kiến hết hàng dựa trên tồn khả dụng và tốc độ bán.",
    )
    needs_replenishment = fields.Boolean(
        string="Cần bổ sung hàng",
        compute="_compute_stock_metrics",
        search="_search_needs_replenishment",
    )

    _sql_constraints = [
        (
            "store_product_unique",
            "unique(store_id, product_id)",
            "Mỗi sản phẩm chỉ được khai báo một lần trong cùng cửa hàng.",
        ),
    ]

    @api.depends("product_id", "location_id", "min_qty", "max_qty")
    def _compute_stock_metrics(self):
        Quant = self.env["stock.quant"].sudo()
        pending_qty_map = defaultdict(float)
        active_states = ("draft", "submitted", "to_approve", "approved", "po_created")

        relevant_lines = self.filtered(lambda line: line.store_id and line.product_id)
        if relevant_lines:
            request_lines = self.env["mer.purchase.request.line"].sudo().search(
                [
                    ("request_id.store_id", "in", relevant_lines.mapped("store_id").ids),
                    ("product_id", "in", relevant_lines.mapped("product_id").ids),
                    ("request_id.state", "in", active_states),
                ]
            )
            for request_line in request_lines:
                request = request_line.request_id
                if not request.store_id:
                    continue
                if hasattr(request, "_is_line_logistically_completed") and request._is_line_logistically_completed(request_line):
                    continue
                pending_qty = request_line.approved_qty or request_line.product_qty
                pending_qty_map[(request.store_id.id, request_line.product_id.id)] += pending_qty

        for line in self:
            current_qty = 0.0
            available_qty = 0.0
            pending_qty = 0.0
            # Safety check for location
            target_location_id = line.location_id.id if line.location_id else None
            
            if line.product_id and target_location_id:
                # Use SQL for absolute isolation at the specific lot location
                self.env.cr.execute("""
                    SELECT SUM(quantity), SUM(quantity - reserved_quantity) 
                    FROM stock_quant 
                    WHERE product_id = %s AND location_id = %s
                """, (line.product_id.id, target_location_id))
                res = self.env.cr.fetchone()
                if res:
                    current_qty = res[0] if res[0] else 0.0
                    available_qty = res[1] if res[1] else 0.0
                
                pending_qty = pending_qty_map.get((line.store_id.id, line.product_id.id), 0.0)
            
            suggested_qty = 0.0
            effective_qty = available_qty + pending_qty
            if effective_qty < line.min_qty:
                suggested_qty = max(line.max_qty - effective_qty, 0.0)
            
            line.current_qty = current_qty
            line.available_qty = available_qty
            line.pending_replenishment_qty = pending_qty
            line.suggested_replenishment_qty = suggested_qty
            line.needs_replenishment = suggested_qty > 0

            # --- NEW: Tính tốc độ bán và ngày tồn ---
            today = fields.Date.today()
            date_30d_ago = today - datetime.timedelta(days=30)
            
            # Lấy doanh số trong 30 ngày qua tại cửa hàng này cho sản phẩm này
            # Note: optimize by doing this outside the loop if possible, but for now this is accurate
            sales_lines = self.env['sale.order.line'].sudo().search([
                ('product_id', '=', line.product_id.id),
                ('order_id.store_id', '=', line.store_id.id),
                ('order_id.state', 'in', ('sale', 'done')),
                ('order_id.date_order', '>=', date_30d_ago)
            ])
            total_sold = sum(sales_lines.mapped('product_uom_qty'))
            velocity = total_sold / 30.0
            line.sales_velocity_30d = velocity
            
            if velocity > 0:
                line.days_of_stock = available_qty / velocity
            else:
                line.days_of_stock = 999.0 if available_qty > 0 else 0.0

    @api.constrains("min_qty", "max_qty")
    def _check_qty_range(self):
        for line in self:
            if line.min_qty < 0 or line.max_qty < 0:
                raise ValidationError("Tồn tối thiểu và tồn tối đa phải lớn hơn hoặc bằng 0.")
            if line.max_qty < line.min_qty:
                raise ValidationError("Tồn tối đa phải lớn hơn hoặc bằng tồn tối thiểu.")



    def _search_needs_replenishment(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise ValidationError("Chỉ hỗ trợ tìm kiếm Có/Không cho cờ cần bổ sung hàng.")

        matched_ids = self.search([]).filtered(lambda line: line.suggested_replenishment_qty > 0).ids
        domain = [("id", "in", matched_ids)]
        return domain if (operator == "=" and value) or (operator == "!=" and not value) else [("id", "not in", matched_ids)]

    def action_create_replenishment_pr(self):
        self.ensure_one()
        if self.suggested_replenishment_qty <= 0:
            raise UserError(_("Sản phẩm này hiện chưa cần bổ sung thêm hàng."))

        duplicate_request = self.env["mer.purchase.request"]._find_duplicate_store_request(
            self.store_id.id,
            [self.product_id.id],
        )
        if duplicate_request:
            raise UserError(
                _(
                    "Sản phẩm này đã có trong PR %(pr)s đang xử lý của cửa hàng. "
                    "Không thể tạo thêm PR trùng."
                )
                % {"pr": duplicate_request.name}
            )

        central_warehouse = self.store_id._get_central_warehouse()
        if not central_warehouse:
            raise UserError(_("Chưa cấu hình Kho tổng để Merchandise xử lý yêu cầu của cửa hàng."))

        request = self.env["mer.purchase.request"].create(
            {
                "store_id": self.store_id.id,
                "warehouse_id": self.store_id.warehouse_id.id,
                "notes": _("PR được tạo từ định mức tồn kho của cửa hàng."),
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_id.id,
                            "product_qty": self.suggested_replenishment_qty,
                        }
                    )
                ],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "mer.purchase.request",
            "res_id": request.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": {
                "from_store_menu": 1,
                "default_store_id": self.store_id.id,
            },
        }
