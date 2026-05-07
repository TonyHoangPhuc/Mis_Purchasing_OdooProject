from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _compute_expiration_date(self):
        # Tách các dòng nhập hàng để xử lý riêng, bao gồm cả trường hợp trong wizard (check qua move_id hoặc context)
        incoming_lines = self.filtered(
            lambda l: (
                l.picking_id.picking_type_code == "incoming" or 
                (l.move_id and l.move_id.picking_id.picking_type_code == "incoming") or
                self.env.context.get("default_picking_type_code") == "incoming" or
                (l.location_id and l.location_id.usage == "supplier") or
                (l.move_id and l.move_id.location_id.usage == "supplier")
            )
            and l.product_id.use_expiration_date
            and not self._context.get("skip_expiry_check")
        )
        other_lines = self - incoming_lines

        if other_lines:
            super(StockMoveLine, other_lines)._compute_expiration_date()

        for line in incoming_lines:
            # Nếu đã có lot_id và lot đó có ngày hết hạn, thì lấy từ lot
            if line.lot_id and line.lot_id.expiration_date:
                line.expiration_date = line.lot_id.expiration_date
            elif not line.expiration_date:
                # Nếu là hàng mới nhập và chưa có ngày, để trống để bắt buộc nhập tay
                line.expiration_date = False

    def _compute_removal_date(self):
        incoming_lines = self.filtered(
            lambda l: (
                l.picking_id.picking_type_code == "incoming" or 
                (l.move_id and l.move_id.picking_id.picking_type_code == "incoming") or
                self.env.context.get("default_picking_type_code") == "incoming" or
                (l.location_id and l.location_id.usage == "supplier") or
                (l.move_id and l.move_id.location_id.usage == "supplier")
            )
            and l.product_id.use_expiration_date
            and not self._context.get("skip_expiry_check")
        )
        other_lines = self - incoming_lines

        if other_lines:
            super(StockMoveLine, other_lines)._compute_removal_date()

        for line in incoming_lines:
            if line.lot_id and line.lot_id.removal_date:
                line.removal_date = line.lot_id.removal_date
            elif line.expiration_date:
                line.removal_date = line.expiration_date
            elif not line.removal_date:
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

    @api.onchange("expiration_date")
    def _onchange_expiration_date_sync_removal(self):
        if self.expiration_date:
            self.removal_date = self.expiration_date

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
