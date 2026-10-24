#!/bin/bash
set -e

GUNICORN_THREADS=${GUNICORN_THREADS:-4}
GUNICORN_WORKERS=${GUNICORN_WORKERS:-2}
GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-120}

exec /home/frappe/frappe-bench/env/bin/gunicorn \
  --chdir=/home/frappe/frappe-bench/sites \
  --bind=127.0.0.1:8000 \
  --threads="$GUNICORN_THREADS" \
  --workers="$GUNICORN_WORKERS" \
  --worker-class=gthread \
  --worker-tmp-dir=/dev/shm \
  --timeout="$GUNICORN_TIMEOUT" \
  --preload \
  frappe.app:application
