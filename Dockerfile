# Sử dụng bản Odoo 19 chính thức làm chuẩn
FROM odoo:19.0

USER root

# Mở port 7860 cho Hugging Face
EXPOSE 7860

# Đưa thư mục custom module của bạn vào container
COPY ./custom_addons /mnt/extra-addons

# Cấp quyền cho user odoo để tránh lỗi Permission Denied
RUN chown -R odoo:odoo /mnt/extra-addons

# Chuyển về lại user odoo (bắt buộc vì lý do bảo mật)
USER odoo

# Lệnh khởi chạy Odoo với các biến môi trường của Supabase
CMD odoo \
    --http-port=7860 \
    --db_host=$DB_HOST \
    --db_port=$DB_PORT \
    --db_user=$DB_USER \
    --db_password=$DB_PASSWORD \
    --proxy-mode \
    --db-filter=^OdooProjectV2$ \
    --limit-time-real=0 \
    --limit-time-cpu=0 \
    -d OdooProjectV2