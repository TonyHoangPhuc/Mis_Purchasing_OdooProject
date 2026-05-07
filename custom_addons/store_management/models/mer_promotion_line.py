from odoo import api, fields, models

class MerPromotionLine(models.Model):
    _inherit = 'mer.promotion.line'

    sale_order_line_ids = fields.One2many('sale.order.line', 'promotion_line_id', string='Dòng đơn hàng')

    @api.depends(
        'sale_order_line_ids.state',
        'sale_order_line_ids.product_uom_qty',
        'sale_order_line_ids.qty_delivered',
        'sale_order_line_ids.move_ids.state',
        'sale_order_line_ids.move_ids.quantity',
        'sale_order_line_ids.move_ids.location_id.usage',
        'sale_order_line_ids.move_ids.location_dest_id.usage',
    )
    def _compute_sold_qty(self):
        for line in self:
            sold_qty = 0.0
            sale_lines = line.sale_order_line_ids.filtered(lambda sale_line: sale_line.state in ['sale', 'done'])

            for sale_line in sale_lines:
                done_delivery_moves = sale_line.move_ids.filtered(
                    lambda move: move.state == 'done'
                    and move.location_id.usage == 'internal'
                    and move.location_dest_id.usage == 'customer'
                )
                sold_qty += sum(done_delivery_moves.mapped('quantity')) if done_delivery_moves else sale_line.qty_delivered

            line.sold_qty = sold_qty

    @api.depends(
        'sale_order_line_ids.state',
        'sale_order_line_ids.product_uom_qty',
        'sale_order_line_ids.qty_delivered',
        'sale_order_line_ids.move_ids.state',
        'sale_order_line_ids.move_ids.quantity',
        'sale_order_line_ids.move_ids.location_id.usage',
        'sale_order_line_ids.move_ids.location_dest_id.usage',
    )
    def _compute_reserved_qty(self):
        for line in self:
            reserved_qty = 0.0
            sale_lines = line.sale_order_line_ids.filtered(lambda sale_line: sale_line.state in ['sale', 'done'])

            for sale_line in sale_lines:
                done_delivery_moves = sale_line.move_ids.filtered(
                    lambda move: move.state == 'done'
                    and move.location_id.usage == 'internal'
                    and move.location_dest_id.usage == 'customer'
                )
                delivered_qty = sum(done_delivery_moves.mapped('quantity')) if done_delivery_moves else sale_line.qty_delivered
                reserved_qty += max(0.0, sale_line.product_uom_qty - delivered_qty)

            line.reserved_qty = reserved_qty
