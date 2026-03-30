#!/bin/bash

echo "Starting Odoo..."

odoo \
  --config=odoo.conf \
  --http-port=$PORT