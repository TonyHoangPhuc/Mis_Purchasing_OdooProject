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
        product_data = []
        for product in picking.move_ids.filtered(
            lambda current_move: current_move.state != "cancel"
        ).mapped("product_id"):
            product_moves = picking.move_ids.filtered(
                lambda current_move: current_move.state != "cancel"
                and current_move.product_id == product
            )
            product_move_lines = picking.move_line_ids.filtered(
                lambda line: line.move_id.state != "cancel"
                and line.product_id == product
                and line.lot_id
            )

            if product.tracking != "none" and product_move_lines:
                lot_data = {}
                for move_line in product_move_lines:
                    lot_data.setdefault(
                        move_line.lot_id.id,
                        {
                            "product_id": product.id,
                            "lot_id": move_line.lot_id.id,
                            "expected_qty": 0.0,
                            "actual_qty": 0.0,
                            "damaged_qty": 0.0,
                            "damage_note": "",
                        },
                    )
                    lot_data[move_line.lot_id.id]["expected_qty"] += move_line.quantity
                    default_actual_qty = move_line.quantity
                    if not picking.store_actual_check_done and not default_actual_qty:
                        default_actual_qty = move_line.quantity
                    lot_data[move_line.lot_id.id]["actual_qty"] += default_actual_qty

                total_damaged_qty = sum(product_moves.mapped("wm_damaged_qty"))
                damage_notes = [note for note in product_moves.mapped("wm_damage_note") if note]
                lot_rows = list(lot_data.values())
                if lot_rows and total_damaged_qty > 0:
                    lot_rows[-1]["damaged_qty"] = total_damaged_qty
                    lot_rows[-1]["damage_note"] = "; ".join(dict.fromkeys(damage_notes))
                product_data.extend(lot_rows)
                continue

            expected_qty = sum(product_moves.mapped("product_uom_qty"))
            actual_qty = sum(product_moves.mapped("quantity"))
            if not picking.store_actual_check_done and not actual_qty:
                actual_qty = expected_qty
            product_data.append(
                {
                    "product_id": product.id,
                    "lot_id": False,
                    "expected_qty": expected_qty,
                    "actual_qty": actual_qty,
                    "damaged_qty": sum(product_moves.mapped("wm_damaged_qty")),
                    "damage_note": "; ".join(
                        dict.fromkeys(
                            [note for note in product_moves.mapped("wm_damage_note") if note]
                        )
                    ),
                }
            )

        res.update(
            {
                "picking_id": picking_id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": values["product_id"],
                            "lot_id": values["lot_id"],
                            "expected_qty": values["expected_qty"],
                            "actual_qty": values["actual_qty"],
                            "damaged_qty": values["damaged_qty"],
                            "damage_note": values["damage_note"],
                        },
                    )
                    for values in product_data
                ],
            }
        )
        return res

    def _write_actual_qty_to_moves(self, product, actual_qty, damaged_qty=0.0, damage_note=False):
        self.ensure_one()
        product_moves = self.picking_id.move_ids.filtered(
            lambda move: move.product_id == product and move.state != "cancel"
        )
        # Giữ lại SL thực nhận thật ở bước QC để người dùng còn nhìn thấy phần dư.
        # Phần cắt về đúng SL PR/PO sẽ chỉ được xử lý khi xác nhận nhập kho.
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

    def _write_actual_qty_to_move_lines(self, wizard_lines):
        self.ensure_one()
        tracked_lines = wizard_lines.filtered("lot_id")
        if not tracked_lines:
            return

        product = tracked_lines[0].product_id
        product_moves = self.picking_id.move_ids.filtered(
            lambda move: move.product_id == product and move.state != "cancel"
        )
        if not product_moves:
            return

        product_move_lines = self.picking_id.move_line_ids.filtered(
            lambda line: line.product_id == product and line.move_id.state != "cancel"
        )
        if product_move_lines:
            product_move_lines.unlink()

        move_capacities = [
            {
                "move": move,
                "remaining_qty": move.quantity,
            }
            for move in product_moves
            if move.quantity > 0
        ]

        for wizard_line in tracked_lines.filtered(lambda line: line.actual_qty > 0):
            remaining_qty = wizard_line.actual_qty
            while remaining_qty > 0 and move_capacities:
                current_slot = move_capacities[0]
                move = current_slot["move"]
                allocated_qty = min(remaining_qty, current_slot["remaining_qty"])
                move_line_vals = move._prepare_move_line_vals(quantity=allocated_qty)
                move_line_vals.update(
                    {
                        "lot_id": wizard_line.lot_id.id,
                        "quantity": allocated_qty,
                    }
                )
                self.env["stock.move.line"].create(move_line_vals)

                remaining_qty -= allocated_qty
                current_slot["remaining_qty"] -= allocated_qty
                if current_slot["remaining_qty"] <= 0:
                    move_capacities.pop(0)

    def _create_or_update_shortage_report(self, product, expected_qty, actual_qty, destination_warehouse):
        report = self.env["mer.discrepancy.report"].search(
            [
                ("picking_id", "=", self.picking_id.id),
                ("product_id", "=", product.id),
                ("reason", "=", "shortage"),
            ],
            limit=1,
        )
        vals = {
            "picking_id": self.picking_id.id,
            "purchase_id": self.picking_id.purchase_id.id,
            "warehouse_id": destination_warehouse.id if destination_warehouse else False,
            "product_id": product.id,
            "expected_qty": expected_qty,
            "actual_qty": actual_qty,
            "reason": "shortage",
            "solution_notes": _("Được tạo tự động từ bước kiểm hàng thực tế tại cửa hàng."),
        }
        if report:
            report.write(vals)
            return report
        return self.env["mer.discrepancy.report"].create(vals)

    def _create_or_update_damaged_report(
        self, product, expected_qty, damaged_qty, damage_note, destination_warehouse
    ):
        report = self.env["mer.discrepancy.report"].search(
            [
                ("picking_id", "=", self.picking_id.id),
                ("product_id", "=", product.id),
                ("reason", "=", "damaged"),
            ],
            limit=1,
        )
        vals = {
            "picking_id": self.picking_id.id,
            "purchase_id": self.picking_id.purchase_id.id,
            "warehouse_id": destination_warehouse.id if destination_warehouse else False,
            "product_id": product.id,
            "expected_qty": expected_qty,
            "actual_qty": 0.0,
            "damaged_qty": damaged_qty,
            "reason": "damaged",
            "solution_notes": _("Phát hiện %s hàng hư hỏng từ bước kiểm hàng thực tế. Ghi chú: %s") % (damaged_qty, damage_note or ""),
        }
        if report:
            report.write(vals)
            return report
        return self.env["mer.discrepancy.report"].create(vals)

    def _prepare_excess_report_line_commands(self, wizard_lines):
        lot_totals = {}
        for line in wizard_lines.filtered("lot_id"):
            lot_totals.setdefault(
                line.lot_id.id,
                {
                    "lot_id": line.lot_id.id,
                    "expected_qty": 0.0,
                    "actual_qty": 0.0,
                },
            )
            lot_totals[line.lot_id.id]["expected_qty"] += line.expected_qty
            lot_totals[line.lot_id.id]["actual_qty"] += line.actual_qty
        return [(5, 0, 0)] + [(0, 0, values) for values in lot_totals.values()]

    def _create_or_update_excess_report(self, product, expected_qty, actual_qty, wizard_lines):
        report = self.env["mer.excess.receipt"].search(
            [
                ("picking_id", "=", self.picking_id.id),
                ("product_id", "=", product.id),
                ("state", "!=", "done"),
            ],
            limit=1,
        )
        vals = {
            "picking_id": self.picking_id.id,
            "product_id": product.id,
            "expected_qty": expected_qty,
            "actual_qty": actual_qty,
            "notes": _("Được tạo tự động từ bước kiểm hàng thực tế tại cửa hàng."),
        }
        line_commands = self._prepare_excess_report_line_commands(wizard_lines)
        if line_commands and len(line_commands) > 1:
            vals["line_ids"] = line_commands
        if report:
            report.write(vals)
            return report
        return self.env["mer.excess.receipt"].create(vals)

    def action_process_qc(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("Không tìm thấy phiếu nhận hàng để kiểm tra."))

        # Xác định lại việc bỏ qua báo cáo dư cho NCC một cách chắc chắn hơn
        is_supplier_receipt = (
            self.picking_id.store_route_type in ("supplier_to_store", "supplier_to_central") or
            (self.picking_id.picking_type_code == "incoming" and not self.picking_id._is_store_receipt_from_central())
        )
        skip_excess_report = is_supplier_receipt
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

        for product in self.line_ids.mapped("product_id"):
            product_lines = self.line_ids.filtered(lambda l: l.product_id == product)
            actual_qty = sum(product_lines.mapped("actual_qty"))
            expected_qty = sum(product_lines.mapped("expected_qty"))
            damaged_qty = sum(product_lines.mapped("damaged_qty"))
            damage_notes = [note for note in product_lines.mapped("damage_note") if note]
            damage_note = "; ".join(dict.fromkeys(damage_notes))

            self._write_actual_qty_to_moves(product, actual_qty, damaged_qty, damage_note)
            self._write_actual_qty_to_move_lines(product_lines)

            if damaged_qty > 0:
                self._create_or_update_damaged_report(
                    product,
                    expected_qty,
                    damaged_qty,
                    damage_note,
                    destination_warehouse,
                )
                created_report_count += 1

            comparison = float_compare(
                actual_qty,
                expected_qty,
                precision_rounding=product.uom_id.rounding or 0.01,
            )
            if comparison > 0:
                if not skip_excess_report:
                    self._create_or_update_excess_report(product, expected_qty, actual_qty, product_lines)
                    created_report_count += 1
                else:
                    excess_messages.append(_("<li>Sản phẩm %s: dư %s cái.</li>") % (product.display_name, actual_qty - expected_qty))
            elif comparison < 0:
                self._create_or_update_shortage_report(product, expected_qty, actual_qty, destination_warehouse)
                created_report_count += 1

        if skip_excess_report:
            existing_excess = self.env["mer.excess.receipt"].search([("picking_id", "=", self.picking_id.id)])
            if existing_excess:
                existing_excess.write(
                    {
                        "state": "cancel",
                        "notes": _("Luồng nhận hàng từ NCC không theo dõi báo cáo nhận dư. Phần hàng dư được xem là trả lại ngay cho NCC."),
                    }
                )

        if excess_messages:
            self.picking_id.message_post(
                body=_("<b>Ghi nhận dư hàng từ NCC (không tạo báo cáo):</b><ul>%s</ul>") % "".join(excess_messages),
                subtype_xmlid="mail.mt_note",
            )

        self.picking_id.write({"store_actual_check_done": True})
        
        # Tạo thông báo tổng hợp các báo cáo đã tạo
        report_links = []
        if created_report_count:
            excess_reports = self.env["mer.excess.receipt"].search(
                [("picking_id", "=", self.picking_id.id), ("state", "!=", "cancel")]
            )
            shortage_reports = self.env["mer.discrepancy.report"].search([("picking_id", "=", self.picking_id.id)])
            
            for r in excess_reports:
                report_links.append(_("<li>Dư hàng: %s (Sản phẩm: %s)</li>") % (r.name, r.product_id.display_name))
            for r in shortage_reports:
                reason_label = _("Thiếu hàng") if r.reason == "shortage" else _("Hàng lỗi")
                report_links.append(_("<li>%s: %s (Sản phẩm: %s)</li>") % (reason_label, r.name, r.product_id.display_name))

        msg_body = _("Đã cập nhật số lượng thực nhận từ bước kiểm hàng thực tế.")
        if report_links:
            msg_body += _("<br/><b>Các báo cáo sai lệch đã tạo/cập nhật:</b><ul>%s</ul>") % "".join(report_links)
        
        self.picking_id.message_post(body=msg_body)

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
    lot_id = fields.Many2one("stock.lot", string="Lô hàng")
    expected_qty = fields.Float(string="SL hệ thống", readonly=True)
    actual_qty = fields.Float(string="SL thực nhận")
    damaged_qty = fields.Float(string="SL hư hỏng")
    damage_note = fields.Char(string="Ghi chú lỗi")
