from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    scm_allocation_plan_id = fields.Many2one(
        "supply.chain.allocation.plan",
        string="Kế hoạch phân bổ",
        copy=False,
        readonly=True,
    )
