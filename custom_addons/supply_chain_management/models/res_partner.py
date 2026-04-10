from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    sc_is_store = fields.Boolean(
        string="Là cửa hàng",
        help="Bật cho đối tác đại diện cửa hàng nhận hàng từ kho trung tâm.",
    )
    sc_store_priority = fields.Selection(
        [
            ("high", "Cao"),
            ("medium", "Trung bình"),
            ("low", "Thấp"),
        ],
        string="Mức ưu tiên cửa hàng",
        default="medium",
    )
