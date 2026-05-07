from odoo import api, fields, models, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    mer_reliability_score = fields.Integer(string="Điểm uy tín (%)", compute="_compute_mer_performance")
    mer_total_po_count = fields.Integer(string="Tổng số PO", compute="_compute_mer_performance")
    mer_total_discrepancy_count = fields.Integer(string="Số lần sai lệch", compute="_compute_mer_performance")
    
    mer_rating = fields.Selection([
        ('excellent', 'Xuất sắc'),
        ('good', 'Tốt'),
        ('average', 'Trung bình'),
        ('poor', 'Cần theo dõi')
    ], string="Đánh giá Merchandise", compute="_compute_mer_performance")

    mer_avg_lead_time = fields.Float(string="Lead-time trung bình (Ngày)", compute="_compute_mer_performance")

    def _compute_mer_performance(self):
        for partner in self:
            # Chỉ tính cho NCC
            pos = self.env['purchase.order'].search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ('purchase', 'done'))
            ])
            partner.mer_total_po_count = len(pos)
            
            # Tính Lead-time trung bình
            total_days = 0.0
            po_with_receipts = 0
            for po in pos:
                # Tìm các phiếu nhập kho đã hoàn tất của PO này
                pickings = po.picking_ids.filtered(lambda p: p.state == 'done' and p.picking_type_code == 'incoming')
                if pickings and po.date_approve:
                    # Lấy ngày hoàn tất cuối cùng
                    last_done_date = max(pickings.mapped('date_done'))
                    delta = (last_done_date.date() - po.date_approve.date()).days
                    total_days += max(0, delta)
                    po_with_receipts += 1
            
            partner.mer_avg_lead_time = total_days / po_with_receipts if po_with_receipts > 0 else 0.0

            # Tính số lần sai lệch từ báo cáo sai lệch
            # Giả sử chúng ta tìm các báo cáo sai lệch liên quan đến các phiếu nhập của NCC này
            discrepancies = self.env['mer.discrepancy.report'].search([
                ('picking_id.partner_id', '=', partner.id),
                ('state', '!=', 'draft')
            ])
            partner.mer_total_discrepancy_count = len(discrepancies)
            
            # Tính điểm uy tín (giả định đơn giản: 100% - 10% cho mỗi lần sai lệch, tối thiểu 0%)
            if partner.mer_total_po_count > 0:
                score = 100 - (partner.mer_total_discrepancy_count * 10)
                partner.mer_reliability_score = max(0, score)
            else:
                partner.mer_reliability_score = 100
                
            # Xếp hạng
            if partner.mer_reliability_score >= 90:
                partner.mer_rating = 'excellent'
            elif partner.mer_reliability_score >= 70:
                partner.mer_rating = 'good'
            elif partner.mer_reliability_score >= 40:
                partner.mer_rating = 'average'
            else:
                partner.mer_rating = 'poor'
