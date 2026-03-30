#!/bin/bash

echo "Starting Odoo..."

odoo \
  -c /etc/odoo/odoo.conf \
  --http-port=$PORT \
  --http-interface=0.0.0.0 \
  --proxy-mode