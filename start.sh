#!/bin/bash

echo "Initializing Odoo database..."

odoo \
  -c /etc/odoo/odoo.conf \
  --http-port=$PORT \
  --proxy-mode \
  -d misproject_mwvg \
  -i base \
  --without-demo=all \
  --stop-after-init