import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _extract_context_id(self, value):
        if not value:
            return None
        if isinstance(value, (list, tuple)) and value:
            value = value[0]
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if hasattr(value, "id"):
            value = value.id
        return value if isinstance(value, int) and value > 0 else None

    def _apply_store_sale_domain(self, domain=None):
        domain = list(domain or [])
        if not self.env.context.get("store_sale_stock_only"):
            return domain

        store_id = self._extract_context_id(
            self.env.context.get("store_id") or self.env.context.get("default_store_id")
        )
        if not store_id:
            warehouse_id = self._extract_context_id(
                self.env.context.get("warehouse") or self.env.context.get("warehouse_id")
            )
            if warehouse_id:
                warehouse = self.env["stock.warehouse"].browse(warehouse_id)
                store_id = warehouse.store_record_id.id

        if not store_id:
            return [("id", "in", [0])] + domain

        store = self.env["store.store"].browse(store_id)
        product_ids = store.product_line_ids.filtered("active").mapped("product_id").ids
        return [("id", "in", product_ids or [0])] + domain

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        domain = self._apply_store_sale_domain(domain)
        return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = self._apply_store_sale_domain(args)
        return super().name_search(name, args, operator, limit)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        domain = self._apply_store_sale_domain(domain)
        return super().web_search_read(
            domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )
