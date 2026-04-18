import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


_logger = logging.getLogger(__name__)


class MerDeliveryDiscrepancyWizard(models.TransientModel):
    _name = "mer.delivery.discrepancy.wizard"
    _description = "Wizard kiểm hàng thực tế"

    picking_id = fields.Many2one("stock.picking", string="Phiếu kho", readonly=True)
    line_ids = fields.One2many(
        "mer.delivery.discrepancy.wizard.line",
        "wizard_id",
        string="Chi tiết sản phẩm",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking_id = self.env.context.get("active_id")
        if not picking_id:
            return res

        picking = self.env["stock.picking"].browse(picking_id)
        product_data = {}
        for move in picking.move_ids.filtered(lambda current_move: current_move.state != "cancel"):
            product_data.setdefault(
                move.product_id.id,
                {
                    "product_id": move.product_id.id,
                    "expected_qty": 0.0,
                },
            )
            product_data[move.product_id.id]["expected_qty"] += move.product_uom_qty

        res.update(
            {
                "picking_id": picking_id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": values["product_id"],
                            "expected_qty": values["expected_qty"],
                            "actual_qty": values["expected_qty"],
                        },
                    )
                    for values in product_data.values()
                ],
            }
        )
        return res

    def _write_actual_qty_to_moves(self, product, actual_qty):
        self.ensure_one()
        product_moves = self.picking_id.move_ids.filtered(
            lambda move: move.product_id == product and move.state != "cancel"
        )
        remaining_qty = actual_qty
        move_count = len(product_moves)
        for index, move in enumerate(product_moves):
            move_qty = (
                remaining_qty
                if index == move_count - 1
                else min(move.product_uom_qty, remaining_qty)
            )
            move.quantity = max(move_qty, 0.0)
            remaining_qty -= move_qty

    def action_process_qc(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("Không tìm thấy phiếu nhận hàng để kiểm tra."))

        destination_warehouse = (
            self.picking_id.location_dest_id.warehouse_id
            or self.picking_id.picking_type_id.warehouse_id
        )
        discrepancy_ids = []

        for line in self.line_ids:
            if line.actual_qty < 0:
                raise UserError(_("Số lượng thực nhận không được âm."))

            actual_qty = line.actual_qty
            if self.picking_id._is_central_supplier_receipt() and line.actual_qty > line.expected_qty:
                actual_qty = line.expected_qty

            self._write_actual_qty_to_moves(line.product_id, actual_qty)

            if float_compare(
                actual_qty,
                line.expected_qty,
                precision_rounding=line.product_id.uom_id.rounding or 0.01,
            ):
                if self.picking_id._is_central_supplier_receipt() and actual_qty >= line.expected_qty:
                    continue
                discrepancy = self.env["mer.discrepancy.report"].create(
                    {
                        "picking_id": self.picking_id.id,
                        "purchase_id": self.picking_id.purchase_id.id,
                        "warehouse_id": destination_warehouse.id if destination_warehouse else False,
                        "product_id": line.product_id.id,
                        "expected_qty": line.expected_qty,
                        "actual_qty": actual_qty,
                        "reason": "overage" if actual_qty > line.expected_qty else "shortage",
                        "solution_notes": _(
                            "Được tạo tự động từ bước kiểm hàng thực tế tại cửa hàng."
                        ),
                    }
                )
                discrepancy_ids.append(discrepancy.id)

        self.picking_id.write({"store_actual_check_done": True})

        self.picking_id.message_post(
            body=_("Đã cập nhật số lượng thực nhận từ bước kiểm hàng thực tế."),
        )

        if not discrepancy_ids:
            return {"type": "ir.actions.act_window_close"}

        action = {
            "name": _("Báo cáo sai lệch nhận hàng"),
            "type": "ir.actions.act_window",
            "res_model": "mer.discrepancy.report",
        }
        if len(discrepancy_ids) == 1:
            action.update(
                {
                    "res_id": discrepancy_ids[0],
                    "view_mode": "form",
                    "views": [(False, "form")],
                }
            )
        else:
            action.update(
                {
                    "domain": [("id", "in", discrepancy_ids)],
                    "view_mode": "list,form",
                    "views": [(False, "list"), (False, "form")],
                }
            )
        return action


class MerDeliveryDiscrepancyWizardLine(models.TransientModel):
    _name = "mer.delivery.discrepancy.wizard.line"
    _description = "Chi tiết kiểm hàng thực tế"

    wizard_id = fields.Many2one("mer.delivery.discrepancy.wizard")
    product_id = fields.Many2one("product.product", string="Sản phẩm")
    expected_qty = fields.Float(string="SL hệ thống", readonly=True)
    actual_qty = fields.Float(string="SL thực nhận")
