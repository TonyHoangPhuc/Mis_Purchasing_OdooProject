FROM odoo:18

USER root

COPY ./custom_addons /mnt/extra-addons
COPY ./odoo.conf /etc/odoo/odoo.conf
COPY ./start.sh /start.sh

RUN chmod +x /start.sh

CMD ["/start.sh"]