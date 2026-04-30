# Sử dụng bản Odoo 19 chính thức làm chuẩn
FROM odoo:19.0

USER root

# Mở port 7860 cho Hugging Face
EXPOSE 7860

# Đưa thư mục custom module vào container
COPY ./custom_addons /mnt/extra-addons

# Cấp quyền cho user odoo
RUN chown -R odoo:odoo /mnt/extra-addons

USER odoo

# Lệnh khởi chạy tối ưu
CMD odoo \
    --http-port=7860 \
    --db_host=$DB_HOST \
    --db_port=$DB_PORT \
    --db_user=$DB_USER \
    --db_password=$DB_PASSWORD \
    --proxy-mode \
    --db-filter=^OdooProjectV3$ \
    --limit-time-real=0 \
    --limit-time-cpu=0 \
    -d OdooProjectV2