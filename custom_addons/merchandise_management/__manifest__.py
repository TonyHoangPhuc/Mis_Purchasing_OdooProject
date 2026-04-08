{
    'name': 'Merchandise Management',
    'version': '1.0',
    'summary': 'Quản lý nghiệp vụ Merchandise trên Odoo 19',
    'description': """
        Module quản lý các nghiệp vụ của Merchandise bao gồm:
        - Nhận thông tin tồn kho (Overstock, Understock)
        - Quản lý tạm dừng đặt hàng (Stop Ordering)
        - Phê duyệt quy trình Purchase Request (PR)
        - Tạo Purchase Order (PO) từ PR
        - Gửi PO cho Warehouse
        - Xử lý sai lệch hàng hóa
    """,
    'category': 'Purchase',
    'author': 'Your Name',
    'depends': ['purchase', 'stock', 'product', 'uom', 'mail', 'purchase_stock'],
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
