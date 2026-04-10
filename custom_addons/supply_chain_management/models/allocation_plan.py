from collections import defaultdict

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class SupplyChainAllocationPlan(models.Model):
    _name = "supply.chain.allocation.plan"
    _description = "Kế hoạch phân bổ chuỗi cung ứng"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_date desc, id desc"

    name = fields.Char(
        string="Mã kế hoạch",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Kho",
        required=True,
        tracking=True,
    )
    source_location_id = fields.Many2one(
        "stock.location",
        string="Vị trí nguồn",
        required=True,
        domain="[('usage', '=', 'internal')]",
        tracking=True,
    )
    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Loại điều chuyển",
        required=True,
        domain="[('code', '=', 'internal')]",
        tracking=True,
    )
    planned_date = fields.Datetime(
        string="Ngày dự kiến",
        default=fields.Datetime.now,
        tracking=True,
    )
    product_ids = fields.Many2many(
        "product.product",
        string="Bộ lọc sản phẩm",
        help="Để trống để tạo đề xuất từ tất cả quy tắc phân bổ đang hoạt động của kho này.",
    )
    line_ids = fields.One2many(
        "supply.chain.allocation.line",
        "plan_id",
        string="Dòng phân bổ",
    )
    picking_ids = fields.One2many(
        "stock.picking",
        "scm_allocation_plan_id",
        string="Điều chuyển",
    )
    transfer_count = fields.Integer(
        string="Số phiếu điều chuyển",
        compute="_compute_transfer_count",
    )
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("suggested", "Đã đề xuất"),
            ("confirmed", "Đã xác nhận"),
            ("cancelled", "Đã hủy"),
        ],
        string="Trạng thái",
        default="draft",
        tracking=True,
    )
    note = fields.Text(string="Ghi chú")
    company_id = fields.Many2one(
        "res.company",
        related="warehouse_id.company_id",
        string="Công ty",
        store=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = sequence.next_by_code("supply.chain.allocation.plan") or _("New")
        return super().create(vals_list)

    @api.depends("picking_ids")
    def _compute_transfer_count(self):
        for plan in self:
            plan.transfer_count = len(plan.picking_ids)

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        if self.warehouse_id:
            self.source_location_id = self.warehouse_id.lot_stock_id
            self.picking_type_id = self.warehouse_id.int_type_id

    def action_generate_suggestions(self):
        Quant = self.env["stock.quant"].sudo()
        Rule = self.env["supply.chain.allocation.rule"]
        for plan in self:
            rule_domain = [("warehouse_id", "=", plan.warehouse_id.id), ("active", "=", True)]
            if plan.product_ids:
                rule_domain.append(("product_id", "in", plan.product_ids.ids))
            rules = Rule.search(rule_domain)
            if not rules:
                raise UserError("Không tìm thấy quy tắc phân bổ đang hoạt động cho kho này.")

            # Allocate available DC stock by priority to avoid rebuilding reservation logic.
            source_available_by_product = defaultdict(float)
            for product in rules.mapped("product_id"):
                quants = Quant.search(
                    [
                        ("product_id", "=", product.id),
                        ("location_id", "child_of", plan.source_location_id.id),
                    ]
                )
                source_available_by_product[product.id] = sum(quants.mapped("available_quantity"))

            commands = [Command.clear()]
            allocated_by_product = defaultdict(float)
            sorted_rules = rules.sorted(
                key=lambda rule: (
                    PRIORITY_ORDER.get(rule.store_priority or "medium", 1),
                    rule.partner_id.display_name or "",
                    rule.product_id.display_name or "",
                )
            )
            for rule in sorted_rules:
                on_hand_qty = rule.current_qty
                demand_qty = rule.replenishment_need_qty
                available_qty = max(
                    source_available_by_product[rule.product_id.id] - allocated_by_product[rule.product_id.id],
                    0.0,
                )
                suggested_qty = min(demand_qty, available_qty)
                shortage_qty = max(demand_qty - suggested_qty, 0.0)
                allocated_by_product[rule.product_id.id] += suggested_qty
                commands.append(
                    Command.create(
                        {
                            "rule_id": rule.id,
                            "partner_id": rule.partner_id.id,
                            "destination_location_id": rule.location_id.id,
                            "product_id": rule.product_id.id,
                            "priority": rule.store_priority,
                            "min_qty": rule.min_qty,
                            "max_qty": rule.max_qty,
                            "on_hand_qty": on_hand_qty,
                            "demand_qty": demand_qty,
                            "suggested_qty": suggested_qty,
                            "shortage_qty": shortage_qty,
                        }
                    )
                )
            plan.write({"line_ids": commands, "state": "suggested"})

    def action_create_internal_transfers(self):
        StockPicking = self.env["stock.picking"]
        StockMove = self.env["stock.move"]
        for plan in self:
            if not plan.line_ids:
                raise UserError("Hãy tạo đề xuất trước khi tạo phiếu điều chuyển nội bộ.")

            lines_to_transfer = plan.line_ids.filtered(
                lambda line: line.suggested_qty > 0 and not line.transfer_picking_id
            )
            if not lines_to_transfer:
                raise UserError("Không có dòng đề xuất hợp lệ để tạo điều chuyển.")

            pickings_by_location = {}
            for line in lines_to_transfer.sorted(key=lambda l: l.destination_location_id.complete_name or ""):
                picking = pickings_by_location.get(line.destination_location_id.id)
                if not picking:
                    picking = StockPicking.create(
                        {
                            "picking_type_id": plan.picking_type_id.id,
                            "location_id": plan.source_location_id.id,
                            "location_dest_id": line.destination_location_id.id,
                            "origin": plan.name,
                            "scheduled_date": plan.planned_date,
                            "scm_allocation_plan_id": plan.id,
                        }
                    )
                    pickings_by_location[line.destination_location_id.id] = picking

                StockMove.create(
                    {
                        "product_id": line.product_id.id,
                        "description_picking": line.product_id.display_name,
                        "product_uom_qty": line.suggested_qty,
                        "product_uom": line.product_id.uom_id.id,
                        "location_id": plan.source_location_id.id,
                        "location_dest_id": line.destination_location_id.id,
                        "picking_id": picking.id,
                    }
                )
                line.transfer_picking_id = picking.id

            created_pickings = self.env["stock.picking"].browse([picking.id for picking in pickings_by_location.values()])
            created_pickings.action_confirm()
            created_pickings.action_assign()
            plan.state = "confirmed"

    def action_reset_to_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        for plan in self:
            if any(picking.state == "done" for picking in plan.picking_ids):
                raise UserError("Không thể hủy kế hoạch phân bổ đã có phiếu điều chuyển hoàn tất.")
            draft_pickings = plan.picking_ids.filtered(lambda picking: picking.state not in ("done", "cancel"))
            if draft_pickings:
                draft_pickings.action_cancel()
            plan.state = "cancelled"

    def action_view_transfers(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        action["domain"] = [("id", "in", self.picking_ids.ids)]
        action["context"] = {
            "default_picking_type_id": self.picking_type_id.id,
            "default_location_id": self.source_location_id.id,
        }
        if len(self.picking_ids) == 1:
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
            action["res_id"] = self.picking_ids.id
        return action


class SupplyChainAllocationLine(models.Model):
    _name = "supply.chain.allocation.line"
    _description = "Dòng phân bổ chuỗi cung ứng"
    _order = "priority, partner_id, product_id"

    plan_id = fields.Many2one(
        "supply.chain.allocation.plan",
        string="Kế hoạch phân bổ",
        required=True,
        ondelete="cascade",
    )
    rule_id = fields.Many2one(
        "supply.chain.allocation.rule",
        string="Quy tắc phân bổ",
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cửa hàng",
        required=True,
        readonly=True,
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Vị trí đích",
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Sản phẩm",
        required=True,
        readonly=True,
    )
    priority = fields.Selection(
        [
            ("high", "Cao"),
            ("medium", "Trung bình"),
            ("low", "Thấp"),
        ],
        string="Mức ưu tiên",
        readonly=True,
    )
    min_qty = fields.Float(
        string="Tồn tối thiểu",
        digits="Product Unit of Measure",
        readonly=True,
    )
    max_qty = fields.Float(
        string="Tồn tối đa",
        digits="Product Unit of Measure",
        readonly=True,
    )
    on_hand_qty = fields.Float(
        string="Tồn hiện có",
        digits="Product Unit of Measure",
        readonly=True,
    )
    demand_qty = fields.Float(
        string="Nhu cầu",
        digits="Product Unit of Measure",
        readonly=True,
    )
    suggested_qty = fields.Float(
        string="Số lượng đề xuất",
        digits="Product Unit of Measure",
        readonly=True,
    )
    shortage_qty = fields.Float(
        string="Số lượng thiếu",
        digits="Product Unit of Measure",
        readonly=True,
    )
    transfer_picking_id = fields.Many2one(
        "stock.picking",
        string="Phiếu điều chuyển",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="plan_id.company_id",
        string="Công ty",
        store=True,
        readonly=True,
    )
