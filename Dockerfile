# Sử dụng bản Odoo 17 chính thức làm chuẩn
FROM odoo:17.0
USER root
EXPOSE 7860

# Trả lại quyền bảo mật cho user odoo
USER odoo

# Lệnh khởi động Odoo
CMD odoo \
    --http-port=7860 \
    --db_host=$DB_HOST \
    --db_port=$DB_PORT \
    --db_user=$DB_USER \
    --db_password=$DB_PASSWORD \
    --proxy-mode \
    --db-filter=.* \
    --limit-time-real=0 \
    --limit-time-cpu=0 \
    -d OdooProjectV1
