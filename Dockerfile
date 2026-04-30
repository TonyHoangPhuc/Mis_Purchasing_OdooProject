# Use the official Odoo image.
FROM odoo:19.0

USER root

# Hugging Face Spaces exposes the app on port 7860.
EXPOSE 7860

# Copy custom modules into Odoo's extra addons path.
COPY ./custom_addons /mnt/extra-addons
RUN chown -R odoo:odoo /mnt/extra-addons

USER odoo

# ODOO_MASTER_PASSWORD is the master password for Odoo's database manager.
# Use this value on the "Create Database" screen. It is not the same as
# DB_PASSWORD, which is only the PostgreSQL user's password.
CMD odoo \
    --http-port=7860 \
    --db_host=${DB_HOST} \
    --db_port=${DB_PORT:-5432} \
    --db_user=${DB_USER} \
    --db_password=${DB_PASSWORD} \
    --admin-passwd=${ODOO_MASTER_PASSWORD:-admin} \
    --proxy-mode \
    --db-filter=^OdooProjectV2$ \
    --limit-time-real=0 \
    --limit-time-cpu=0 \
    -d OdooProjectV2
