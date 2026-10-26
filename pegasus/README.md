# Frappe HR on Pegasus

INOMO runs Frappe HR and ERPNext on [Pegasus](https://codeberg.org/inomotech/pegasus-cluster) from
this branch (`pegasus-v16`). Everything is public: the HRMS fixes, this folder and the image
`ghcr.io/inomotech-foss/hrms`.

The image contains Frappe, ERPNext, HRMS from this branch and
[ERPNextSwiss](https://github.com/libracore/erpnextswiss). The versions are pinned in `apps.json`
and `Containerfile`. `.github/workflows/pegasus.yaml` builds it on every push to this branch.

| App | URL | Purpose |
|---|---|---|
| `erp-sandbox` | https://erp-sandbox.apps.svc.inomo.tech | Test data. Follows `pegasus-v16`. Safe to wipe. |
| `hr` | https://hr.apps.svc.inomo.tech | Not set up yet. Real HR data once the sandbox has passed. |

Pegasus' Argo CD only reads `github.com/inomotech/*` today. Registering the app below needs
`https://github.com/inomotech-foss/*` added to `sourceRepos` in pegasus-cluster.

## How it runs

Each app is one pod, because every Frappe process needs the `sites` volume and Pegasus
volumes are ReadWriteOnce:

- `redis-cache` and `redis-queue`: sidecars, no persistence
- `init`: `resources/pegasus-init.sh`. Writes the config, creates the site
  on the first start, installs missing apps and runs `bench migrate`. Runs before every start.
- `frontend` (nginx, port 8080), `backend` (gunicorn), `websocket`, `worker`, `scheduler`

The database is a Pegasus `PostgresDatabase` (Postgres 18). Frappe calls Postgres support
experimental, and HRMS is not tested on it. Testing that is the sandbox's job.

Differences from the stock frappe_docker image:

- The `frappe` user is UID 10001, as Pegasus requires.
- The Postgres client is 18. `pg_dump` 17 cannot back up a Postgres 18 server.
- nginx drops the `Authorization` header. The gateway sets it to the Entra token, and Frappe
  rejects every request with a bearer token it does not know.
- `resources/postgres-compat.sql` adds `ifnull()`, which ERPNextSwiss uses in raw SQL.
- `resources/sitecustomize.py` makes psycopg2 return JSON columns as strings, as MariaDB
  does. Without it, Frappe fails on `DocField.link_filters` when a customization of
  Customer is saved, which breaks the ERPNextSwiss install.

This branch is HRMS tag `v16.52.0` plus Postgres fixes plus this folder. To update, rebase it
onto the next HRMS tag, and offer the fixes upstream.

## Login

There is no Frappe login. The Pegasus gateway signs everyone in with Entra, and
`apps/pegasus_auth` signs the same user into Frappe from the gateway's `X-Auth-Request-*`
headers:

- Unknown users are created on their first visit as Employee Self Service users. They get that
  role once HR links them to their Employee (field `User ID`).
- `deploy/<app>/pegasus-auth.json` lists Entra object IDs with extra roles. These users become
  System Users with those roles. Roles are only added, never removed. Currently Nils Armbruster
  and Frank Wagner get System Manager, HR Manager and HR User.
- Disabled users are not signed in.
- Logging out of Frappe redirects to `/oauth2/logout`, which signs out of Entra and all Pegasus
  apps. Otherwise the headers would sign the user straight back in.
- Requests without the headers (health checks) are not signed in. `Administrator` is only
  needed from `bench`.

## Postgres status

ERPNext 16 still has MariaDB-only code; Frappe calls Postgres support experimental, and
HRMS is not tested on it upstream. ERPNext develop (v17) is fixing this, so we backport and
fix as we find problems, in three places:

- `resources/postgres-compat.sql`: MariaDB functions as SQL functions (`ifnull`, `if`,
  `datediff`, `curdate`).
- `resources/sitecustomize.py`: JSON columns as strings, no index hints (`FORCE INDEX`).
- `apps/pegasus_compat`: functions backported from ERPNext develop, installed before every
  request and job. So far `item_query` (the item search behind every Item field). Remove a
  backport once the ERPNext version in `apps.json` has the fix.

Works on Pegasus: install, SSO, the Profit and Loss Statement, item search, the bank import
pages. Payroll and the ERPNextSwiss salary features are not tested yet.

## First deploy of an app

There are no secrets to create. The database login comes from the `PostgresDatabase`, and
Frappe's encryption key is created on the first start and kept in `site_config.json` on the
`sites` volume. It must never change, or stored passwords and API keys can no longer be read,
so keep the volume (it is backed up daily, and `bench backup` saves the site config too).
The `Administrator` password is random and never used; sign-in is SSO.

1. Wait until CI has built an image and set its tag in `pegasus/deploy/erp-sandbox/kustomization.yaml`.

2. Register the app:

   ```sh
   argocd login argocd.svc.inomo.tech --sso --grpc-web
   # --validate=false: validating clones the large HRMS repo inside the request, which
   # runs into the gateway timeout (504). Argo CD clones it in the background instead.
   argocd app create erp-sandbox --validate=false \
     --project apps \
     --repo https://github.com/inomotech-foss/hrms \
     --revision pegasus-v16 \
     --path pegasus/deploy/erp-sandbox \
     --dest-server https://kubernetes.default.svc \
     --dest-namespace app-erp-sandbox \
     --sync-policy automated --auto-prune --self-heal \
     --sync-option CreateNamespace=true
   argocd app logs erp-sandbox --kind Deployment --name frappe --container init --follow
   ```

   The first start installs all apps and takes about 3 minutes, plus the image pull.

3. Open the app. You are signed in with your Entra account (see "Login"). An HR manager runs
   the setup wizard.

## Operating

```sh
argocd app get erp-sandbox
argocd app logs erp-sandbox --kind Deployment --name frappe --container backend --tail 100
argocd app actions run erp-sandbox restart --kind Deployment --resource-name frappe
```

For `bench` commands, open a terminal on the `backend` container in the Argo CD web UI.

## Updating

Rebase onto the new HRMS tag, change the tags in `apps.json` (and `FRAPPE_BRANCH` in `Containerfile`)
and push. CI builds the
image and deploys it to `erp-sandbox`, and the init container runs `bench migrate`. `hr` gets the
tag by hand once the sandbox has run it.
