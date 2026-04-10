from collections import defaultdict

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    sm_show_supplier_performance = fields.Boolean(
        string="Hiển thị trong hiệu suất nhà cung cấp",
        compute="_compute_supplier_metrics",
        search="_search_sm_show_supplier_performance",
    )
    lead_time_avg = fields.Float(
        string="Lead time trung bình (ngày)",
        compute="_compute_supplier_metrics",
        digits=(16, 2),
    )
    on_time_delivery_rate = fields.Float(
        string="Tỷ lệ giao đúng hạn (%)",
        compute="_compute_supplier_metrics",
        digits=(16, 2),
        search="_search_on_time_delivery_rate",
    )
    delivery_accuracy_rate = fields.Float(
        string="Độ chính xác giao hàng (%)",
        compute="_compute_supplier_metrics",
        digits=(16, 2),
    )
    quality_score = fields.Float(
        string="Điểm chất lượng (%)",
        compute="_compute_supplier_metrics",
        digits=(16, 2),
        search="_search_quality_score",
    )
    supplier_rating = fields.Selection(
        [
            ("1", "1 - Kém"),
            ("2", "2 - Trung bình"),
            ("3", "3 - Khá"),
            ("4", "4 - Tốt"),
            ("5", "5 - Xuất sắc"),
        ],
        string="Xếp hạng nhà cung cấp",
        default="3",
    )
    supplier_purchase_count = fields.Integer(
        string="Đơn mua",
        compute="_compute_supplier_metrics",
    )
    supplier_receipt_count = fields.Integer(
        string="Phiếu nhập",
        compute="_compute_supplier_metrics",
    )

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
                partner.supplier_rank > 0 or supplier_purchases or supplier_receipts
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

                # Quality is weighted by usable quantity after QC and damage tracking.
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
        visible_partners = (purchase_partners | receipt_partners | self.search([("supplier_rank", ">", 0)])).ids

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
        return [("id", "in", matched_partners.ids)]

    def _search_on_time_delivery_rate(self, operator, value):
        return self._search_metric_value("on_time_delivery_rate", operator, value)

    def _search_quality_score(self, operator, value):
        return self._search_metric_value("quality_score", operator, value)

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
