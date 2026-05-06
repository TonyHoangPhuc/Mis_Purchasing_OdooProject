from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _compute_expiration_date(self):
        super()._compute_expiration_date()
        for line in self:
            if (
                line.picking_type_use_create_lots
                and not line.lot_id
                and line.product_id.use_expiration_date
                and (line.product_id.expiration_time or 0) <= 0
            ):
                line.expiration_date = False

    def _compute_removal_date(self):
        super()._compute_removal_date()
        for line in self:
            if (
                line.picking_type_use_create_lots
                and not line.lot_id
                and line.product_id.use_expiration_date
                and (line.product_id.removal_time or 0) <= 0
            ):
                line.removal_date = False

    def _should_auto_generate_vendor_lot(self):
        self.ensure_one()
        picking = self.picking_id
        return bool(
            picking
            and self.product_id
            and self.product_id.tracking != "none"
            and picking.picking_type_code == "incoming"
            and picking.state not in ("done", "cancel")
            and (picking.location_id.usage == "supplier" or picking.purchase_id)
        )

    def _apply_vendor_lot_defaults(self):
        sequence = self.env["ir.sequence"]
        for line in self:
            vals = {}
            if (
                line._should_auto_generate_vendor_lot()
                and float_compare(
                    line.quantity or 0.0,
                    0.0,
                    precision_rounding=line.product_uom_id.rounding or 0.01,
                ) > 0
                and not line.lot_id
                and not line.lot_name
            ):
                vals["lot_name"] = sequence.next_by_code("store_management.auto_stock_lot") or sequence.next_by_code(
                    "stock.lot.serial"
                )
            if vals:
                super(StockMoveLine, line.with_context(skip_vendor_lot_defaults=True)).write(vals)

    def _prepare_new_lot_vals(self):
        vals = super()._prepare_new_lot_vals()
        if self.removal_date:
            vals["removal_date"] = self.removal_date
        return vals

    def _create_and_assign_production_lot(self):
        auto_vendor_lines = self.filtered(lambda line: line._should_auto_generate_vendor_lot())
        remaining_lines = self - auto_vendor_lines

        if remaining_lines:
            super(StockMoveLine, remaining_lines)._create_and_assign_production_lot()

        if not auto_vendor_lines:
            return

        lot_vals = []
        key_to_index = {}
        key_to_mls = defaultdict(lambda: self.env["stock.move.line"])
        for ml in auto_vendor_lines:
            key = (ml.product_id.id, ml.lot_name)
            key_to_mls[key] |= ml
            if ml.tracking != "lot" or key not in key_to_index:
                key_to_index[key] = len(lot_vals)
                lot_vals.append(ml._prepare_new_lot_vals())

        lots = self.env["stock.lot"].with_context(skip_auto_expiry_defaults=True).create(lot_vals)
        for key, mls in key_to_mls.items():
            lot = lots[key_to_index[key]].with_prefetch(lots._ids)
            mls.with_prefetch(self._prefetch_ids).write({"lot_id": lot.id})

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get("skip_vendor_lot_defaults"):
            lines._apply_vendor_lot_defaults()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_vendor_lot_defaults"):
            self._apply_vendor_lot_defaults()
        return res
