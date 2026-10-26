#!/bin/bash
# Runs as the init container before every start: writes the bench config,
# creates the site on the first start, installs missing apps and migrates.
#
# /mnt/db  Secret main-postgres from the PostgresDatabase
set -euo pipefail

: "${SITE_NAME:?}"
: "${INSTALL_APPS:?}"

cd /home/frappe/frappe-bench

db_host=$(cat /mnt/db/host)
db_port=$(cat /mnt/db/port)
db_name=$(cat /mnt/db/dbname)
db_user=$(cat /mnt/db/username)
db_password=$(cat /mnt/db/password)

cp -r --update=none /opt/pegasus-sites/. sites/
ls -1 apps > sites/apps.txt
bench set-config -g db_type postgres
bench set-config -g db_host "$db_host"
bench set-config -gp db_port "$db_port"
bench set-config -g redis_cache redis://127.0.0.1:6379
bench set-config -g redis_queue redis://127.0.0.1:6380
bench set-config -g redis_socketio redis://127.0.0.1:6380
bench set-config -gp socketio_port 9000
bench set-config -g chromium_path /usr/lib/chromium/chromium-headless-shell

PGHOST=$db_host PGPORT=$db_port PGDATABASE=$db_name PGUSER=$db_user PGPASSWORD=$db_password \
  psql -v ON_ERROR_STOP=1 -q -f /opt/pegasus/postgres-compat.sql

if [ ! -f "sites/$SITE_NAME/site_config.json" ]; then
  echo "Creating site $SITE_NAME"
  bench new-site "$SITE_NAME" \
    --db-type postgres \
    --no-setup-db \
    --db-host "$db_host" \
    --db-port "$db_port" \
    --db-name "$db_name" \
    --db-user "$db_user" \
    --db-password "$db_password" \
    --admin-password "$(env/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
    --set-default
fi

# Applying the PostgresDatabase again issues a new password.
bench --site "$SITE_NAME" set-config db_password "$db_password"

# Encrypts stored passwords and API keys. It lives only in site_config.json on
# the sites volume and must never change. Created here once, so that no two
# processes race to create it on first use.
if ! jq -e .encryption_key "sites/$SITE_NAME/site_config.json" >/dev/null; then
  bench --site "$SITE_NAME" set-config encryption_key \
    "$(env/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
fi

bench --site "$SITE_NAME" set-config host_name "https://$SITE_NAME"
bench --site "$SITE_NAME" set-config --parse pegasus_auth "${PEGASUS_AUTH:-"{}"}"

installed=$(bench --site "$SITE_NAME" list-apps --format json | jq -r --arg site "$SITE_NAME" '.[$site][]')
for app in $INSTALL_APPS; do
  if ! grep -qx "$app" <<<"$installed"; then
    echo "Installing $app"
    bench --site "$SITE_NAME" install-app "$app"
  fi
done

bench --site "$SITE_NAME" migrate
