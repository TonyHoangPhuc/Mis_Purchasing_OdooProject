from collections import defaultdict

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    _supplier_contact_category_name = "NCC"

    is_supplier_contact = fields.Boolean(
        string="L\u00e0 nh\u00e0 cung c\u1ea5p",
        help="\u0110\u00e1nh d\u1ea5u \u0111\u1ed1i t\u00e1c n\u00e0y l\u00e0 nh\u00e0 cung c\u1ea5p \u0111\u1ec3 c\u00f3 th\u1ec3 ch\u1ecdn trong nghi\u1ec7p v\u1ee5 mua h\u00e0ng.",
        compute="_compute_is_supplier_contact",
        inverse="_inverse_is_supplier_contact",
        search="_search_is_supplier_contact",
    )
    sm_show_supplier_performance = fields.Boolean(
        string="Hi\u1ec3n th\u1ecb trong hi\u1ec7u su\u1ea5t nh\u00e0 cung c\u1ea5p",
        compute="_compute_supplier_metrics",
        search="_search_sm_show_supplier_performance",
    )
    lead_time_avg = fields.Float(
        string="Th\u1eddi gian giao trung b\u00ecnh (ng\u00e0y)",
        compute="_compute_supplier_metrics",
        digits=(16, 2),
    )
    on_time_delivery_rate = fields.Float(
        string="T\u1ef7 l\u1ec7 giao \u0111\u00fang h\u1ea1n (%)",
        compute="_compute_supplier_metrics",
        digits=(16, 2),
        search="_search_on_time_delivery_rate",
    )
    delivery_accuracy_rate = fields.Float(
        string="\u0110\u1ed9 ch\u00ednh x\u00e1c giao h\u00e0ng (%)",
        compute="_compute_supplier_metrics",
        digits=(16, 2),
    )
    quality_score = fields.Float(
        string="\u0110i\u1ec3m ch\u1ea5t l\u01b0\u1ee3ng (%)",
        compute="_compute_supplier_metrics",
        digits=(16, 2),
        search="_search_quality_score",
    )
    supplier_rating = fields.Selection(
        [
            ("1", "1 - K\u00e9m"),
            ("2", "2 - Trung b\u00ecnh"),
            ("3", "3 - Kh\u00e1"),
            ("4", "4 - T\u1ed1t"),
            ("5", "5 - Xu\u1ea5t s\u1eafc"),
        ],
        string="X\u1ebfp h\u1ea1ng nh\u00e0 cung c\u1ea5p",
        default="3",
    )
    supplier_purchase_count = fields.Integer(
        string="\u0110\u01a1n mua",
        compute="_compute_supplier_metrics",
    )
    supplier_receipt_count = fields.Integer(
        string="Phi\u1ebfu nh\u1eadp",
        compute="_compute_supplier_metrics",
    )

    def _get_supplier_contact_category(self, create_if_missing=False):
        category = self.env["res.partner.category"].sudo().search(
            [("name", "=", self._supplier_contact_category_name)],
            limit=1,
        )
        if not category and create_if_missing:
            category = self.env["res.partner.category"].sudo().create(
                {"name": self._supplier_contact_category_name}
            )
        return category

    def _get_supplier_filter_domain(self):
        category = self._get_supplier_contact_category()
        if category:
            return [("category_id", "in", category.ids)]
        return [("id", "=", 0)]

    @api.depends("category_id")
    def _compute_is_supplier_contact(self):
        category = self._get_supplier_contact_category()
        for partner in self:
            partner.is_supplier_contact = bool(category and category in partner.category_id)

    def _inverse_is_supplier_contact(self):
        category = self._get_supplier_contact_category(create_if_missing=True)
        for partner in self:
            if partner.is_supplier_contact:
                if partner.supplier_rank <= 0:
                    partner.supplier_rank = 1
                partner.category_id = [(4, category.id)]
            else:
                partner.supplier_rank = 0
                partner.category_id = [(3, category.id)]

    def _search_is_supplier_contact(self, operator, value):
        if operator not in ("=", "!="):
            return []

        category = self._get_supplier_contact_category()
        if (operator == "=" and value) or (operator == "!=" and not value):
            return self._get_supplier_filter_domain()
        if category:
            return [("category_id", "not in", category.ids)]
        return []

    @api.depends("supplier_rank", "supplier_rating")
    def _compute_supplier_metrics(self):
        if not self:
            return

        purchases = self.env["purchase.order"].search(
            [
                ("partner_id", "in", self.ids),
                ("state", "=", "purchase"),
            ]
        )
        receipts = self.env["stock.picking"].search(
            [
                ("purchase_id.partner_id", "in", self.ids),
                ("picking_type_code", "=", "incoming"),
                ("state", "=", "done"),
            ]
        )
        purchases_by_supplier = defaultdict(lambda: self.env["purchase.order"])
        for purchase in purchases:
            purchases_by_supplier[purchase.partner_id.id] |= purchase

        receipts_by_supplier = defaultdict(lambda: self.env["stock.picking"])
        for receipt in receipts:
            receipts_by_supplier[receipt.purchase_id.partner_id.id] |= receipt

        for partner in self:
            supplier_purchases = purchases_by_supplier.get(partner.id, self.env["purchase.order"])
            supplier_receipts = receipts_by_supplier.get(partner.id, self.env["stock.picking"])
            partner.sm_show_supplier_performance = bool(
                partner.is_supplier_contact or supplier_purchases or supplier_receipts
            )
            lead_times = []
            on_time_count = 0
            accuracy_scores = []
            total_received_qty = 0.0
            total_accepted_qty = 0.0

            for receipt in supplier_receipts:
                baseline_date = receipt.purchase_id.date_approve or receipt.purchase_id.date_order
                if baseline_date and receipt.date_done:
                    lead_times.append((receipt.date_done - baseline_date).total_seconds() / 86400.0)

                promised_date = receipt.scheduled_date or receipt.purchase_id.date_planned
                if promised_date and receipt.date_done and receipt.date_done <= promised_date:
                    on_time_count += 1

                expected_qty = receipt.wm_expected_qty
                received_qty = receipt.wm_received_qty
                damaged_qty = receipt.wm_damaged_qty
                total_received_qty += received_qty

                if expected_qty:
                    mismatch_ratio = abs(received_qty - expected_qty) / expected_qty
                    accuracy_scores.append(max(0.0, (1.0 - mismatch_ratio) * 100.0))

                accepted_qty = 0.0 if receipt.wm_qc_status == "rejected" else max(received_qty - damaged_qty, 0.0)
                total_accepted_qty += accepted_qty

            partner.lead_time_avg = sum(lead_times) / len(lead_times) if lead_times else 0.0
            partner.on_time_delivery_rate = (
                on_time_count / len(supplier_receipts) * 100.0 if supplier_receipts else 0.0
            )
            partner.delivery_accuracy_rate = (
                sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0.0
            )
            partner.quality_score = (
                total_accepted_qty / total_received_qty * 100.0 if total_received_qty else 0.0
            )
            partner.supplier_purchase_count = len(supplier_purchases)
            partner.supplier_receipt_count = len(supplier_receipts)

    def _search_sm_show_supplier_performance(self, operator, value):
        if operator not in ("=", "!="):
            return []

        purchase_partners = self.env["purchase.order"].search([("state", "=", "purchase")]).mapped("partner_id")
        receipt_partners = self.env["stock.picking"].search(
            [("picking_type_code", "=", "incoming"), ("state", "=", "done"), ("purchase_id", "!=", False)]
        ).mapped("purchase_id.partner_id")
        visible_partners = (
            purchase_partners
            | receipt_partners
            | self.search(self._get_supplier_filter_domain())
        ).ids

        if (operator == "=" and value) or (operator == "!=" and not value):
            return [("id", "in", visible_partners)]
        return [("id", "not in", visible_partners)]

    def _search_metric_value(self, field_name, operator, value):
        suppliers = self.search([("sm_show_supplier_performance", "=", True)])
        if operator in (">", ">=", "<", "<=", "!=", "="):
            matched_partners = suppliers.filtered(
                lambda partner: (
                    (operator == ">" and partner[field_name] > value)
                    or (operator == ">=" and partner[field_name] >= value)
                    or (operator == "<" and partner[field_name] < value)
                    or (operator == "<=" and partner[field_name] <= value)
                    or (operator == "=" and partner[field_name] == value)
                    or (operator == "!=" and partner[field_name] != value)
                )
            )
            return [("id", "in", matched_partners.ids)]
        return [("id", "in", suppliers.ids)]

    def _search_on_time_delivery_rate(self, operator, value):
        return self._search_metric_value("on_time_delivery_rate", operator, value)

    def _search_quality_score(self, operator, value):
        return self._search_metric_value("quality_score", operator, value)

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = list(args or [])
        if self.env.context.get("only_supplier_contacts"):
            category = self._get_supplier_contact_category()
            if category:
                args.append(("category_id", "in", category.ids))
            else:
                args.append(("id", "=", 0))
        return super().name_search(name, args, operator, limit)

    def action_view_supplier_purchase_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_form_action")
        purchase_orders = self.env["purchase.order"].search(
            [
                ("partner_id", "=", self.id),
                ("state", "=", "purchase"),
            ]
        )
        action["domain"] = [("id", "in", purchase_orders.ids)]
        action["context"] = {"default_partner_id": self.id, "create": False}
        if len(purchase_orders) == 1:
            action["res_id"] = purchase_orders.id
            action["views"] = [(False, "form")]
        return action

    def action_view_supplier_receipts(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        receipts = self.env["stock.picking"].search(
            [
                ("purchase_id.partner_id", "=", self.id),
                ("picking_type_code", "=", "incoming"),
            ]
        )
        action["domain"] = [("id", "in", receipts.ids)]
        action["context"] = {"default_partner_id": self.id, "create": False}
        if len(receipts) == 1:
            action["res_id"] = receipts.id
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        return action
