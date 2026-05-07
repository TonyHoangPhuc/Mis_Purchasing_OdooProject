from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def write(self, vals):
        tracked_fields = {"state", "date_approve", "order_line"}
        tracked_orders = self.filtered(lambda order: order.state in ("purchase", "done"))
        result = super().write(vals)
        if tracked_fields & set(vals):
            tracked_orders |= self.filtered(lambda order: order.state in ("purchase", "done"))
            if tracked_orders:
                self.env["mer.purchase.budget"].sudo()._refresh_usage_metrics()
        return result

    def unlink(self):
        tracked_orders = self.filtered(lambda order: order.state in ("purchase", "done"))
        result = super().unlink()
        if tracked_orders:
            self.env["mer.purchase.budget"].sudo()._refresh_usage_metrics()
        return result


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @staticmethod
    def _has_budget_relevant_changes(vals):
        return bool(
            {"product_id", "product_qty", "price_unit", "price_subtotal", "order_id"} & set(vals)
        )

    def create(self, vals_list):
        lines = super().create(vals_list)
        confirmed_orders = lines.mapped("order_id").filtered(lambda order: order.state in ("purchase", "done"))
        if confirmed_orders:
            self.env["mer.purchase.budget"].sudo()._refresh_usage_metrics()
        return lines

    def write(self, vals):
        should_refresh_budget = self._has_budget_relevant_changes(vals)
        confirmed_orders = self.mapped("order_id").filtered(lambda order: order.state in ("purchase", "done"))
        result = super().write(vals)
        if should_refresh_budget:
            confirmed_orders |= self.mapped("order_id").filtered(lambda order: order.state in ("purchase", "done"))
            if confirmed_orders:
                self.env["mer.purchase.budget"].sudo()._refresh_usage_metrics()
        return result

    def unlink(self):
        confirmed_orders = self.mapped("order_id").filtered(lambda order: order.state in ("purchase", "done"))
        result = super().unlink()
        if confirmed_orders:
            self.env["mer.purchase.budget"].sudo()._refresh_usage_metrics()
        return result
