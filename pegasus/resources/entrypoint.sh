#!/bin/bash
set -e

umask 0002

# Link the assets built into the image into the sites volume.
ASSETS_PATH="/home/frappe/frappe-bench/sites/assets"
rm -rf "$ASSETS_PATH"
ln -s /home/frappe/frappe-bench/assets "$ASSETS_PATH"

exec "$@"
