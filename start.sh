#!/bin/bash

echo "Fixing Odoo missing modules..."

odoo \
  -c /etc/odoo/odoo.conf \
  --http-port=$PORT \
  --http-interface=0.0.0.0 \
  --proxy-mode \
  -d misproject_mwvg \
  -i web \
  --without-demo=all \
  --stop-after-init