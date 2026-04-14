{
    'name': 'Merchandise Management',
    'version': '1.0',
    'summary': 'Quản lý nghiệp vụ Merchandise trên Odoo 19',
    'description': """
        Module quản lý các nghiệp vụ của Merchandise bao gồm:
        - Nhận thông tin tồn kho (thừa hàng, thiếu hàng)
        - Quản lý tạm dừng đặt hàng
        - Phê duyệt quy trình phiếu yêu cầu mua hàng (PR)
        - Tạo đơn mua hàng (PO) từ PR
        - Gửi PO cho Kho
        - Xử lý sai lệch hàng hóa
    """,
    'category': 'Merchandise Management', # Phân loại app trên dashboard
    'author': 'Your Name',
    # Các module Odoo tiêu chuẩn cần cài đặt trước
    'depends': ['purchase', 'stock', 'product', 'uom', 'mail', 'purchase_stock'],
    # Thứ tự nạp các file dữ liệu và giao diện
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/product_template_views.xml',
        'views/mer_purchase_request_views.xml',
        'views/mer_promotion_views.xml',
        'views/mer_discrepancy_report_views.xml',
        'views/merchandise_menus.xml',
    ],
    'installable': True,
    'application': True, 
}
