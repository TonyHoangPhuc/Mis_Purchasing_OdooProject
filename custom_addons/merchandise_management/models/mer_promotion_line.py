from odoo import api, fields, models


class MerPromotionLine(models.Model):
    _name = 'mer.promotion.line'
    _description = 'Promotion Line'

    promotion_id = fields.Many2one('mer.promotion', string='Promotion', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    discount_rate = fields.Float(string='Discount (%)')
    qty_in_stores = fields.Float(string='Store Qty', compute='_compute_qty_in_stores')
    default_code = fields.Char(related='product_id.default_code', string='SKU')
    lst_price = fields.Float(related='product_id.lst_price', string='List Price')

    @api.depends('product_id', 'promotion_id.target_store_ids')
    def _compute_qty_in_stores(self):
        for line in self:
            warehouses = line.promotion_id.target_store_ids
            if not warehouses:
                line.qty_in_stores = 0.0
                continue

            quants = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id.warehouse_id', 'in', warehouses.ids),
                ('quantity', '>', 0),
            ])
            line.qty_in_stores = sum(quants.mapped('quantity'))
