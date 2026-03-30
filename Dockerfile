FROM odoo:18

USER root

# Copy config + addons
COPY ./custom_addons /mnt/extra-addons
COPY ./odoo.conf /etc/odoo/odoo.conf

# Expose port
EXPOSE 10000

# Run Odoo
CMD ["odoo", "-c", "/etc/odoo/odoo.conf", "--http-port=10000"]