from odoo import models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def action_view_inventory(self):
        action = super().action_view_inventory()
        context = dict(action.get("context") or {})
        context["search_default_not_expired_lots"] = 1
        action["context"] = context
        return action
