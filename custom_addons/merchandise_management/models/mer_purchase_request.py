import operator as py_operator

from markupsafe import escape

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
    
    price_unit = fields.Float(string='Đơn giá dự kiến', digits='Product Price')
    price_subtotal = fields.Float(string='Thành tiền', compute='_compute_price_subtotal', store=True)
    budget_id = fields.Many2one(
        "mer.purchase.budget",
        string="Ngân sách áp dụng",
        copy=False,
        domain="[('state', '=', 'active')]",
        help="Ngân sách sẽ được dùng để kiểm tra hạn mức cho dòng sản phẩm này.",
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            # Kiểm tra trạng thái vòng đời SKU
            if self.product_id.x_mer_sku_lifecycle == 'discontinued':
                product_name = self.product_id.name
                self.product_id = False
                return {
                    'warning': {
                        'title': _('Sản phẩm ngừng kinh doanh'),
                        'message': _('Sản phẩm "%s" đã ngừng kinh doanh. Không thể tạo yêu cầu mua hàng.') % product_name
                    }
                }
            elif self.product_id.x_mer_sku_lifecycle == 'phase_out':
                return {
                    'warning': {
                        'title': _('Sản phẩm đang xả hàng'),
                        'message': _('Sản phẩm "%s" đang trong giai đoạn xả hàng (Phase-out). Vui lòng cân nhắc kỹ trước khi nhập thêm.') % self.product_id.name
                    }
                }

            self.product_uom_id = self.product_id.uom_id
            # Lấy giá vốn của sản phẩm làm giá dự kiến ban đầu
            self.price_unit = self.product_id.standard_price
            self._suggest_budget()
            
    @api.depends('product_qty', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_qty * line.price_unit

    @api.onchange('product_id', 'supplier_id')
    def _onchange_product_id_price(self):
        if self.product_id:
            # 1. Ưu tiên lấy giá từ NCC tại dòng (Tab Phương án xử lý)
            # 2. Nếu dòng không có NCC, lấy giá từ NCC trên Header phiếu
            partner = getattr(self, 'supplier_id', False) or self.request_id.partner_id
            
            if partner:
                supplier_info = self.product_id.seller_ids.filtered(lambda s: s.partner_id == partner)[:1]
                if supplier_info:
                    self.price_unit = supplier_info.price
                    return
            
            # 3. Nếu hoàn toàn không có NCC, lấy giá tiêu chuẩn của sản phẩm
            self.price_unit = self.product_id.standard_price

    def _suggest_budget(self, force=False):
        for line in self:
            if not line.product_id or not line.request_id:
                continue
            if line.budget_id and not force:
                continue
            line.budget_id = line.request_id._find_active_budget_for_category(
                line.product_id.categ_id,
                line.request_id._get_budget_date(),
            )

    @api.onchange("product_id", "request_id.date_request")
    def _onchange_budget_candidate(self):
        self._suggest_budget(force=True)

    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute(
            """
            SELECT to_regclass('mer_purchase_budget'),
                   to_regclass('product_category'),
                   to_regclass('product_template')
            """
        )
        if not all(self.env.cr.fetchone()):
            return res
        self.env.cr.execute(
            """
            UPDATE mer_purchase_request_line line
               SET budget_id = budget_match.id
              FROM mer_purchase_request request,
                   product_product product,
                   product_template template,
                   product_category category,
                   LATERAL (
                       SELECT budget.id
                         FROM mer_purchase_budget budget
                         JOIN product_category budget_category
                           ON budget_category.id = budget.category_id
                        WHERE budget.state = 'active'
                          AND budget.date_from <= request.date_request
                          AND budget.date_to >= request.date_request
                          AND (
                              category.id = budget.category_id
                              OR category.parent_path LIKE budget.category_id::text || '/%'
                              OR category.parent_path LIKE '%/' || budget.category_id::text || '/%'
                          )
                        ORDER BY LENGTH(COALESCE(budget_category.parent_path, '')) DESC,
                                 budget.date_from DESC,
                                 budget.id DESC
                        LIMIT 1
                   ) AS budget_match
             WHERE line.request_id = request.id
               AND line.product_id = product.id
               AND product.product_tmpl_id = template.id
               AND template.categ_id = category.id
               AND line.budget_id IS NULL
            """
        )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.filtered(lambda line: not line.budget_id)._suggest_budget()
        return lines

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
    date_request = fields.Date(
        string='Ngày yêu cầu',
        default=lambda self: fields.Date.context_today(self),
    )
    
    line_ids = fields.One2many('mer.purchase.request.line', 'request_id', string='Chi tiết sản phẩm')
    
    amount_total = fields.Float(string='Tổng tiền dự kiến', compute='_compute_amount_total', store=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Điều khoản thanh toán')
    
    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for request in self:
            request.amount_total = sum(line.price_subtotal for line in request.line_ids)

    x_mer_budget_info = fields.Html(string='Thông tin ngân sách', compute='_compute_x_mer_budget_info')

    @api.depends('line_ids.price_subtotal', 'line_ids.product_id.categ_id')
    def _compute_x_mer_budget_info(self):
        for request in self:
            cat_amounts = {}
            for line in request.line_ids:
                cat = line.product_id.categ_id
                cat_amounts[cat] = cat_amounts.get(cat, 0.0) + line.price_subtotal
            
            html = "<div class='alert alert-light'>"
            for cat, amount in cat_amounts.items():
                if not cat:
                    continue
                budget = self.env['mer.purchase.budget'].search([
                    ('category_id', '=', cat.id),
                    ('state', '=', 'active'),
                    ('date_from', '<=', fields.Date.today()),
                    ('date_to', '>=', fields.Date.today()),
                ], limit=1)
                
                status_color = "green"
                if not budget:
                    status_text = "Không có ngân sách thiết lập"
                    status_color = "gray"
                elif budget.remaining_amount < amount:
                    status_text = "VƯỢT NGÂN SÁCH (Còn: {:,.0f})".format(budget.remaining_amount)
                    status_color = "red"
                else:
                    status_text = "Trong tầm kiểm soát (Còn: {:,.0f})".format(budget.remaining_amount)
                
                html += f"<li><b>{cat.name}:</b> {status_text} <span style='color: {status_color};'>●</span></li>"
            html += "</div>"
            request.x_mer_budget_info = html if cat_amounts else False
    
    def _get_budget_date(self):
        self.ensure_one()
        return self.date_request or fields.Date.context_today(self)

    @api.onchange("date_request")
    def _onchange_date_request_budget(self):
        for line in self.line_ids:
            line._suggest_budget(force=True)

    @api.model
    def _get_category_and_parents(self, category):
        categories = self.env["product.category"]
        while category:
            categories |= category
            category = category.parent_id
        return categories

    def _find_active_budget_for_category(self, category, budget_date):
        self.ensure_one()
        categories = self._get_category_and_parents(category)
        if not categories:
            return self.env["mer.purchase.budget"]

        budgets = self.env["mer.purchase.budget"].search(
            [
                ("category_id", "in", categories.ids),
                ("state", "=", "active"),
                ("date_from", "<=", budget_date),
                ("date_to", ">=", budget_date),
            ]
        )
        for category_id in categories.ids:
            budget = budgets.filtered(lambda current: current.category_id.id == category_id)[:1]
            if budget:
                return budget
        return self.env["mer.purchase.budget"]

    def _is_budget_valid_for_category(self, budget, category, budget_date):
        self.ensure_one()
        if not budget or not category:
            return False
        return bool(
            budget.state == "active"
            and budget.date_from <= budget_date <= budget.date_to
            and category.id in self.env["product.category"].search(
                [("id", "child_of", budget.category_id.id)]
            ).ids
        )

    def _get_budget_hint_for_category(self, category, budget_date):
        self.ensure_one()
        categories = self._get_category_and_parents(category)
        if not categories:
            return _("Sản phẩm chưa có ngành hàng")

        budgets = self.env["mer.purchase.budget"].search(
            [("category_id", "in", categories.ids)],
            order="date_from desc, id desc",
        )
        if not budgets:
            return _("Không có ngân sách thiết lập")

        active_outside_period = budgets.filtered(lambda budget: budget.state == "active")[:1]
        if active_outside_period:
            return _("Ngân sách không áp dụng cho ngày yêu cầu %s") % budget_date

        draft_budget = budgets.filtered(lambda budget: budget.state == "draft")[:1]
        if draft_budget:
            return _("Ngân sách đã tạo nhưng chưa kích hoạt")

        closed_budget = budgets.filtered(lambda budget: budget.state == "closed")[:1]
        if closed_budget:
            return _("Ngân sách đã đóng")

        return _("Không có ngân sách đang áp dụng")

    def _get_budget_summary(self):
        self.ensure_one()
        summary = {}
        budget_date = self._get_budget_date()
        for line in self.line_ids:
            category = line.product_id.categ_id
            if not category:
                continue

            invalid_budget_hint = False
            if line.budget_id:
                if self._is_budget_valid_for_category(line.budget_id, category, budget_date):
                    budget = line.budget_id
                else:
                    budget = self.env["mer.purchase.budget"]
                    invalid_budget_hint = _(
                        "Ngân sách đã chọn (%s) không hợp lệ cho ngành hàng/ngày yêu cầu"
                    ) % line.budget_id.display_name
            else:
                budget = self._find_active_budget_for_category(category, budget_date)
            key = ("budget", budget.id) if budget else ("missing", category.id)
            if key not in summary:
                summary[key] = {
                    "amount": 0.0,
                    "budget": budget,
                    "category_names": set(),
                    "line_budgets": set(),
                    "hint": False,
                }
                if invalid_budget_hint:
                    summary[key]["hint"] = invalid_budget_hint
                elif not budget:
                    summary[key]["hint"] = self._get_budget_hint_for_category(category, budget_date)
            summary[key]["amount"] += line.price_subtotal
            summary[key]["category_names"].add(category.display_name)
            if line.budget_id:
                summary[key]["line_budgets"].add(line.budget_id.display_name)
        return list(summary.values())

    @api.depends('line_ids.price_subtotal', 'line_ids.product_id.categ_id', 'date_request')
    def _compute_x_mer_budget_info(self):
        for request in self:
            items = request._get_budget_summary()
            if not items:
                request.x_mer_budget_info = False
                continue

            html = "<div class='alert alert-light'>"
            for item in items:
                amount = item["amount"]
                budget = item["budget"]
                category_label = ", ".join(sorted(item["category_names"]))

                status_color = "green"
                if not budget:
                    status_text = item["hint"] or _("Không có ngân sách thiết lập")
                    status_color = "gray"
                elif budget.remaining_amount < amount:
                    status_text = _("VƯỢT NGÂN SÁCH (Còn: {:,.0f})").format(budget.remaining_amount)
                    status_color = "red"
                else:
                    status_text = _("Trong tầm kiểm soát (Còn: {:,.0f})").format(budget.remaining_amount)

                if budget and budget.category_id.display_name not in item["category_names"]:
                    category_label = _("%(categories)s (ngân sách: %(budget)s)") % {
                        "categories": category_label,
                        "budget": budget.category_id.display_name,
                    }

                html += (
                    "<li><b>{category}</b>: {status} "
                    "<span style='color: {color};'>●</span></li>"
                ).format(
                    category=escape(category_label),
                    status=escape(status_text),
                    color=status_color,
                )
            html += "</div>"
            request.x_mer_budget_info = html

    def _validate_budget_selection(self):
        for request in self:
            budget_date = request._get_budget_date()
            for line in request.line_ids:
                if not line.product_id:
                    continue
                if not line.budget_id:
                    raise UserError(
                        _("Dòng sản phẩm %s chưa chọn Ngân sách áp dụng.")
                        % line.product_id.display_name
                    )
                if not request._is_budget_valid_for_category(
                    line.budget_id,
                    line.product_id.categ_id,
                    budget_date,
                ):
                    raise UserError(
                        _(
                            "Ngân sách %(budget)s không hợp lệ cho sản phẩm %(product)s "
                            "hoặc ngày yêu cầu %(date)s."
                        )
                        % {
                            "budget": line.budget_id.display_name,
                            "product": line.product_id.display_name,
                            "date": budget_date,
                        }
                    )

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

    # Cập nhật giá sản phẩm khi đổi NCC
    @api.onchange('partner_id')
    def _onchange_partner_id_prices(self):
        for line in self.line_ids:
            line._onchange_product_id_price()

    # Gửi yêu cầu mua hàng
    def action_submit(self):
        for request in self:
            if not request.line_ids:
                raise UserError(_("Bạn không thể gửi yêu cầu khi chưa chọn sản phẩm nào!"))
        self.write({'state': 'submitted'})

    # Gửi lên Quản lý duyệt
    def action_send_to_manager(self):
        for request in self:
            if not request.payment_term_id:
                raise UserError(_("Vui lòng chọn Điều khoản thanh toán trước khi trình Quản lý!"))
        self.write({'state': 'to_approve'})

    # Phê duyệt yêu cầu
    def action_approve(self):
        for request in self:
            # Kiểm tra ngân sách theo từng ngành hàng trong PR
            cat_amounts = {}
            for line in request.line_ids:
                cat = line.product_id.categ_id
                cat_amounts[cat] = cat_amounts.get(cat, 0.0) + line.price_subtotal
            
            for cat, amount in cat_amounts.items():
                if not cat:
                    continue
                budget = self.env['mer.purchase.budget'].search([
                    ('category_id', '=', cat.id),
                    ('state', '=', 'active'),
                    ('date_from', '<=', fields.Date.today()),
                    ('date_to', '>=', fields.Date.today()),
                ], limit=1)
                if budget and budget.remaining_amount < amount:
                    raise UserError(_("Vượt ngân sách ngành hàng '%s'! Ngân sách còn lại: %s, Yêu cầu: %s") % (
                        cat.name, "{:,.0f}".format(budget.remaining_amount), "{:,.0f}".format(amount)))
        
        self.write({'state': 'approved', 'manager_id': self.env.user.id})

    # Từ chối yêu cầu
    def action_approve(self):
        self._validate_budget_selection()
        for request in self:
            for item in request._get_budget_summary():
                budget = item["budget"]
                amount = item["amount"]
                if budget and budget.remaining_amount < amount:
                    category_label = ", ".join(sorted(item["category_names"]))
                    raise UserError(
                        _("Vượt ngân sách ngành hàng '%s'! Ngân sách còn lại: %s, Yêu cầu: %s")
                        % (
                            category_label,
                            "{:,.0f}".format(budget.remaining_amount),
                            "{:,.0f}".format(amount),
                        )
                    )

        self.write({'state': 'approved', 'manager_id': self.env.user.id})

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

        # Lọc các dòng hợp lệ (Sản phẩm không bị dừng đặt hàng)
        stopped_lines = self.line_ids.filtered(lambda l: l.product_id.x_mer_stop_ordering)
        valid_lines = self.line_ids - stopped_lines
        
        if not valid_lines:
            self.action_cancel()
            msg = _("Tất cả sản phẩm trong yêu cầu đều đang dừng đặt hàng. Hệ thống đã tự động hủy yêu cầu này.")
            self.message_post(body=msg)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Yêu cầu bị hủy'),
                    'message': msg,
                    'sticky': True,
                    'type': 'danger',
                }
            }

        purchase_vals = {
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'date_order': fields.Datetime.now(),
            'payment_term_id': self.payment_term_id.id,
            'order_line': [],
        }
        
        for line in valid_lines:
            purchase_vals['order_line'].append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_qty': line.approved_qty if hasattr(line, 'approved_qty') else line.product_qty,
                'product_uom_id': line.product_uom_id.id,
                'price_unit': line.price_unit,
                'date_planned': fields.Datetime.now(),
            }))
            
        purchase_id = self.env['purchase.order'].sudo().create(purchase_vals)
        # Tự động xác nhận đơn hàng (Confirm Order)
        purchase_id.button_confirm()
        
        self.write({'state': 'done'})
        
        if stopped_lines:
            stopped_names = ", ".join(stopped_lines.mapped('product_id.name'))
            self.message_post(body=_("Lưu ý: Các sản phẩm sau đã bị bỏ qua do đang dừng đặt hàng: %s") % stopped_names)

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
