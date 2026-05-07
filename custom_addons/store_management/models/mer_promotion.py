from odoo import models, fields

class MerPromotion(models.Model):
    _inherit = 'mer.promotion'

    target_store_ids = fields.Many2many(
        'stock.warehouse', 
        domain=[('mis_role', '=', 'store')]
    )
