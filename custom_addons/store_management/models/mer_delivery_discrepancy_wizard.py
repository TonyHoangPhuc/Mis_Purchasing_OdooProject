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
                    "actual_qty": 0.0,
                    "damaged_qty": 0.0,
                    "damage_note": "",
                },
            )
            product_data[move.product_id.id]["expected_qty"] += move.product_uom_qty
            default_actual_qty = move.quantity
            if not picking.store_actual_check_done and not default_actual_qty:
                default_actual_qty = move.product_uom_qty
            product_data[move.product_id.id]["actual_qty"] += default_actual_qty
            product_data[move.product_id.id]["damaged_qty"] += move.wm_damaged_qty
            if move.wm_damage_note:
                product_data[move.product_id.id]["damage_note"] = move.wm_damage_note

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
                            "actual_qty": values["actual_qty"],
                            "damaged_qty": values["damaged_qty"],
                            "damage_note": values["damage_note"],
                        },
                    )
                    for values in product_data.values()
                ],
            }
        )
        return res

    def _write_actual_qty_to_moves(self, product, actual_qty, damaged_qty=0.0, damage_note=False):
        self.ensure_one()
        product_moves = self.picking_id.move_ids.filtered(
            lambda move: move.product_id == product and move.state != "cancel"
        )
        remaining_qty = actual_qty
        remaining_damaged_qty = damaged_qty
        move_count = len(product_moves)
        for index, move in enumerate(product_moves):
            move_qty = remaining_qty if index == move_count - 1 else min(move.product_uom_qty, remaining_qty)
            move_damaged_qty = remaining_damaged_qty if index == move_count - 1 else min(move_qty, remaining_damaged_qty)

            move.write({
                'quantity': max(move_qty, 0.0),
                'wm_damaged_qty': max(move_damaged_qty, 0.0),
                'wm_damage_note': damage_note if move_damaged_qty > 0 else False
            })

            remaining_qty -= move_qty
            remaining_damaged_qty -= move_damaged_qty

    def _create_or_update_shortage_report(self, line, actual_qty, destination_warehouse):
        report = self.env["mer.discrepancy.report"].search(
            [
                ("picking_id", "=", self.picking_id.id),
                ("product_id", "=", line.product_id.id),
                ("reason", "=", "shortage"),
            ],
            limit=1,
        )
        vals = {
            "picking_id": self.picking_id.id,
            "purchase_id": self.picking_id.purchase_id.id,
            "warehouse_id": destination_warehouse.id if destination_warehouse else False,
            "product_id": line.product_id.id,
            "expected_qty": line.expected_qty,
            "actual_qty": actual_qty,
            "reason": "shortage",
            "solution_notes": _("Được tạo tự động từ bước kiểm hàng thực tế tại cửa hàng."),
        }
        if report:
            report.write(vals)
            return report
        return self.env["mer.discrepancy.report"].create(vals)

    def _create_or_update_damaged_report(self, line, destination_warehouse):
        report = self.env["mer.discrepancy.report"].search(
            [
                ("picking_id", "=", self.picking_id.id),
                ("product_id", "=", line.product_id.id),
                ("reason", "=", "damaged"),
            ],
            limit=1,
        )
        vals = {
            "picking_id": self.picking_id.id,
            "purchase_id": self.picking_id.purchase_id.id,
            "warehouse_id": destination_warehouse.id if destination_warehouse else False,
            "product_id": line.product_id.id,
            "expected_qty": line.expected_qty,
            "actual_qty": 0.0,
            "damaged_qty": line.damaged_qty,
            "reason": "damaged",
            "solution_notes": _("Phát hiện %s hàng hư hỏng từ bước kiểm hàng thực tế. Ghi chú: %s") % (line.damaged_qty, line.damage_note or ""),
        }
        if report:
            report.write(vals)
            return report
        return self.env["mer.discrepancy.report"].create(vals)

    def _create_or_update_excess_report(self, line, actual_qty):
        report = self.env["mer.excess.receipt"].search(
            [
                ("picking_id", "=", self.picking_id.id),
                ("product_id", "=", line.product_id.id),
                ("state", "!=", "done"),
            ],
            limit=1,
        )
        vals = {
            "picking_id": self.picking_id.id,
            "product_id": line.product_id.id,
            "expected_qty": line.expected_qty,
            "actual_qty": actual_qty,
            "notes": _("Được tạo tự động từ bước kiểm hàng thực tế tại cửa hàng."),
        }
        if report:
            report.write(vals)
            return report
        return self.env["mer.excess.receipt"].create(vals)

    def action_process_qc(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("Không tìm thấy phiếu nhận hàng để kiểm tra."))

        destination_warehouse = (
            self.picking_id.location_dest_id.warehouse_id
            or self.picking_id.picking_type_id.warehouse_id
        )
        created_report_count = 0
        excess_messages = []

        for line in self.line_ids:
            if line.actual_qty < 0:
                raise UserError(_("Số lượng thực nhận không được âm."))
            if line.damaged_qty < 0:
                raise UserError(_("Số lượng hư hỏng không được âm."))
            if line.damaged_qty > line.actual_qty:
                raise UserError(_("Số lượng hư hỏng không được lớn hơn số lượng thực nhận."))
            if line.damaged_qty > 0 and not line.damage_note:
                raise UserError(_("Vui lòng nhập Ghi chú lỗi cho sản phẩm hư hỏng %s.") % line.product_id.display_name)

            actual_qty = line.actual_qty
            if self.picking_id.store_route_type in ("supplier_to_central", "supplier_to_store") and line.actual_qty > line.expected_qty:
                excess_messages.append(
                    _("<li><b>%s</b>: NCC giao dư %s, đã hoàn trả xe (nhận đúng PO %s).</li>") % (
                        line.product_id.display_name,
                        line.actual_qty - line.expected_qty,
                        line.expected_qty,
                    )
                )
                actual_qty = line.expected_qty

            self._write_actual_qty_to_moves(line.product_id, actual_qty, line.damaged_qty, line.damage_note)

            if line.damaged_qty > 0:
                self._create_or_update_damaged_report(line, destination_warehouse)
                created_report_count += 1

            comparison = float_compare(
                actual_qty,
                line.expected_qty,
                precision_rounding=line.product_id.uom_id.rounding or 0.01,
            )
            if comparison != 0:
                if self.picking_id.store_route_type in ("supplier_to_central", "supplier_to_store") and actual_qty >= line.expected_qty:
                    pass
                elif actual_qty > line.expected_qty:
                    self._create_or_update_excess_report(line, actual_qty)
                    created_report_count += 1
                else:
                    self._create_or_update_shortage_report(line, actual_qty, destination_warehouse)
                    created_report_count += 1

        if excess_messages:
            self.picking_id.message_post(
                body=_("<b>Ghi nhận dư hàng từ NCC:</b><ul>%s</ul>") % "".join(excess_messages),
                subtype_xmlid="mail.mt_note",
            )

        self.picking_id.write({"store_actual_check_done": True})
        self.picking_id.message_post(
            body=_("Đã cập nhật số lượng thực nhận, số lượng hư hỏng và ghi chú lỗi từ bước kiểm hàng thực tế."),
        )

        message = _("Đã lưu kết quả kiểm hàng thực tế.")
        if created_report_count:
            message = _("Đã lưu kết quả kiểm hàng và tạo/cập nhật %s báo cáo sai lệch.") % created_report_count

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Kiểm hàng thực tế"),
                "message": message,
                "sticky": False,
                "type": "success",
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": "stock.picking",
                    "res_id": self.picking_id.id,
                    "view_mode": "form",
                    "views": [(False, "form")],
                    "target": "current",
                },
            },
        }


class MerDeliveryDiscrepancyWizardLine(models.TransientModel):
    _name = "mer.delivery.discrepancy.wizard.line"
    _description = "Chi tiết kiểm hàng thực tế"

    wizard_id = fields.Many2one("mer.delivery.discrepancy.wizard")
    product_id = fields.Many2one("product.product", string="Sản phẩm")
    expected_qty = fields.Float(string="SL hệ thống", readonly=True)
    actual_qty = fields.Float(string="SL thực nhận")
    damaged_qty = fields.Float(string="SL hư hỏng")
    damage_note = fields.Char(string="Ghi chú lỗi")
