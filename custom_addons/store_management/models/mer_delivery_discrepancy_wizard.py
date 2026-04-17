import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class MerDeliveryDiscrepancyWizard(models.TransientModel):
    _name = "mer.delivery.discrepancy.wizard"
    _description = "Wizard Kiểm hàng / Báo dư QC"

    picking_id = fields.Many2one("stock.picking", string="Phiếu kho", readonly=True)
    line_ids = fields.One2many("mer.delivery.discrepancy.wizard.line", "wizard_id", string="Chi tiết sản phẩm")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking_id = self.env.context.get("active_id")
        if picking_id:
            picking = self.env["stock.picking"].browse(picking_id)
            lines = []
            # Group by product to handle multiple lines of the same product
            product_data = {}
            for move in picking.move_ids:
                p_id = move.product_id.id
                if p_id not in product_data:
                    product_data[p_id] = {
                        'product_id': p_id,
                        'expected_qty': 0.0,
                    }
                # Use product_uom_qty (Demand) as what is expected to be received
                product_data[p_id]['expected_qty'] += move.product_uom_qty

            lines = []
            for p_id, vals in product_data.items():
                lines.append((0, 0, {
                    "product_id": vals["product_id"],
                    "expected_qty": vals["expected_qty"],
                    "actual_qty": vals["expected_qty"], # Default to expected so user only adjusts differences
                }))
            
            res.update({
                "picking_id": picking_id,
                "line_ids": lines,
            })
        return res

    def action_process_qc(self):
        """Xử lý kết quả QC: Nếu dư thì tạo báo cáo lệch."""
        created_discrepancy_ids = []
        for line in self.line_ids:
            if line.actual_qty > line.expected_qty:
                # Tạo báo cáo nhận dư hàng
                discrepancy = self.env["mer.excess.receipt"].create({
                    "picking_id": self.picking_id.id,
                    "product_id": line.product_id.id,
                    "expected_qty": line.expected_qty,
                    "actual_qty": line.actual_qty,
                    "state": "draft",
                    "notes": _("Được tạo tự động từ bước Kiểm hàng (QC).")
                })
                discrepancy.action_submit() # Gửi thẳng merchandise
                created_discrepancy_ids.append(discrepancy.id)
        
        if created_discrepancy_ids:
            # Điều hướng đến báo cáo
            action = {
                "name": _("Báo cáo dư hàng (QC)"),
                "type": "ir.actions.act_window",
                "res_model": "mer.excess.receipt",
            }
            if len(created_discrepancy_ids) == 1:
                action.update({
                    "res_id": created_discrepancy_ids[0],
                    "view_mode": "form",
                    "views": [(False, "form")],
                })
            else:
                action.update({
                    "domain": [("id", "in", created_discrepancy_ids)],
                    "view_mode": "list,form",
                    "views": [(False, "list"), (False, "form")],
                })
            return action
        return {"type": "ir.actions.act_window_close"}


class MerDeliveryDiscrepancyWizardLine(models.TransientModel):
    _name = "mer.delivery.discrepancy.wizard.line"
    _description = "Chi tiết QC dòng sản phẩm"

    wizard_id = fields.Many2one("mer.delivery.discrepancy.wizard")
    product_id = fields.Many2one("product.product", string="Sản phẩm")
    expected_qty = fields.Float(string="SL Hệ thống", readonly=True)
    actual_qty = fields.Float(string="SL Thực tế")
