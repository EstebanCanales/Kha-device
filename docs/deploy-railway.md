# Deploying to Railway

The prototype is live at <https://kha-device.up.railway.app> (landing) and <https://kha-device-app.up.railway.app> (backend and dashboard). This guide records how it is set up and how to deploy a change.

Three services in one Railway project. Nothing here is certified for clinical or flight use; it is the same prototype, hosted.

| Service | Source | What it runs |
| --- | --- | --- |
| `backend` | repository root | Django + gunicorn, static files through WhiteNoise |
| `Postgres` | Railway PostgreSQL plugin | the database (real PostgreSQL, as the project requires) |
| `landing` | `landing/` | the static Astro site, served by Caddy |

## One-time setup

```bash
railway login
railway init                      # create the project
railway add --database postgres   # adds the Postgres service
```

Then add the two application services and give each a public domain:

```bash
railway add --service backend --json
railway add --service landing --json
railway domain --service backend --json
railway domain --service landing --json
```

Both are deployed from this repository with `railway up` (see "Deploying"); the landing page is uploaded from the `landing/` folder with `--path-as-root`, so no root-directory setting is needed. A domain can be renamed with `railway domain update <old>.up.railway.app --domain <new> --service <service>`.

### Backend variables

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference to the plugin) |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | a long random value (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) |
| `LANDING_URL` | the public URL of the `landing` service, with a trailing slash |
| `ALLOW_SIGNUP` | `true` only if self-service accounts should be open |
| `SIGNUP_DEMO_SESSION` | `session-kha-001` to let new accounts read the demo session |
| `OPEN_READ_ACCESS` | `true` so every account reads every session (simulated data only) |
| `PUBLIC_DEMO` | `true` so the dashboard opens without an account (simulated data only) |
| `IA_ENGINE` | `rules` (Railway has no local Ollama; the language models stay a local option) |
| `RADIATION_API_KEY` | NASA DONKI key, optional |

`DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` are not needed for the Railway domain: the app adds
`RAILWAY_PUBLIC_DOMAIN` itself and trusts the proxy's `X-Forwarded-Proto` header there. Set them only for a custom domain.

### Landing variables

| Variable | Value |
| --- | --- |
| `PUBLIC_APP_URL` | `https://<backend domain>/app/` (read at build time) |

## Service settings

The start command, the pre-deploy step and the health check live in the Railway service configuration, not in a
file: `railway.json` is deprecated and was not applied in this project. Set them once with the service ID from
`railway service list --json`:

```bash
railway environment edit --environment production --message "Backend start, pre-deploy and health check" --json <<'JSON'
{"services":{"<backend-service-id>":{"deploy":{
  "startCommand":"python manage.py collectstatic --noinput && gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile -",
  "preDeployCommand":"python manage.py migrate --noinput",
  "healthcheckPath":"/healthz/","healthcheckTimeout":120}}}}
JSON
```

Static files are collected in the start command on purpose: the pre-deploy step runs in a separate container, so
files written there never reach the running one.

## Deploying

```bash
railway up --service backend --environment production --ci -m "<summary>"
railway up landing --path-as-root --service landing --environment production --ci -m "<summary>"
```

`.railwayignore` keeps `landing/`, local databases and secrets out of the backend upload. A failed migration stops
the release and the previous one keeps serving.

## Demonstration data

The database is reachable only from inside the project's private network, so data is loaded from the backend itself. The hosted session was loaded once by adding the command to the pre-deploy step for one release and removing it afterwards:

```bash
python manage.py migrate --noinput && python manage.py demo_kha --no-user
```

`--no-user` creates no account, so no generated password reaches the deployment logs; people use accounts created from the sign-up page. The command is safe to repeat: with data already present it adds nothing. Simulated devices report one sample every 30 minutes; the default window is 24 hours.

With an SSH key registered in the Railway account (`railway ssh keys add`), the same command can be run directly:

```bash
railway ssh --service backend --environment production -- python manage.py demo_kha --no-user
```

## Checking a deployment

A release is good when all of these hold:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://kha-device-app.up.railway.app/healthz/          # 200
curl -s -o /dev/null -w "%{http_code}\n" https://kha-device-app.up.railway.app/readyz/           # 200: the database answers
curl -s -o /dev/null -w "%{http_code}\n" https://kha-device-app.up.railway.app/accounts/login/   # 200: templates and static files load
curl -s -o /dev/null -w "%{http_code}\n" https://kha-device.up.railway.app/                      # 200
railway deployment list --service backend --environment production --json                        # newest status is SUCCESS
```

`SUCCESS` alone is not enough: the first release reported it while the site answered 502, because a migration had failed.

## Limits to know

- The sign-up rate limit and the NASA cache live in each worker's memory. With two gunicorn workers the limit is per worker.
- Readings already stored in a local `db.sqlite3` are not copied automatically.
- Renaming a Railway domain retires the old address at once; update `LANDING_URL` on the backend and `PUBLIC_APP_URL` on the landing page, then rebuild the landing page.
- The summary uses the `rules` engine; local language models do not run on Railway.
- Retention, backups and a custom domain are pending decisions.
