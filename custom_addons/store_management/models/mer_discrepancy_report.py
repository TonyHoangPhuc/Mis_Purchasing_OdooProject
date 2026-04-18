from odoo import _, fields, models
from odoo.exceptions import UserError


class MerDiscrepancyReport(models.Model):
    _inherit = "mer.discrepancy.report"

    picking_id = fields.Many2one(
        "stock.picking",
        string="Phieu kho",
        tracking=True,
    )
    mer_request_id = fields.Many2one(
        "mer.purchase.request",
        string="Yeu cau Merchandise",
        related="picking_id.mer_request_id",
        store=True,
        readonly=True,
    )
    submitted_to_merchandise = fields.Boolean(
        string="Da gui Merchandise",
        default=False,
        copy=False,
        tracking=True,
    )

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Chi bao cao o trang thai nhap moi duoc gui Merchandise."))
        if self.submitted_to_merchandise:
            raise UserError(_("Bao cao nay da duoc gui Merchandise."))

        self.write({"submitted_to_merchandise": True})
        self.message_post(
            body=_("Cua hang da gui bao cao sai lech cho bo phan Merchandise."),
            subtype_xmlid="mail.mt_note",
        )
        return True
