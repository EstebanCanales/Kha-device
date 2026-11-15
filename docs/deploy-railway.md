# Deploying to Railway

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

Create the `backend` service from the repository root and the `landing` service with **Root Directory** set to `landing`.

### Backend variables

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference to the plugin) |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | a long random value (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) |
| `LANDING_URL` | the public URL of the `landing` service, with a trailing slash |
| `ALLOW_SIGNUP` | `true` only if self-service accounts should be open |
| `SIGNUP_DEMO_SESSION` | `session-kha-001` to let new accounts read the demo session |
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

After the first deploy, load the simulated session once (it prints the demo user's password a single time):

```bash
railway ssh --service backend -- python manage.py demo_kha
```

Simulated devices report one sample every 30 minutes; the default window is 24 hours.

## Limits to know

- The sign-up rate limit and the NASA cache live in each worker's memory. With two gunicorn workers the limit is per worker.
- Readings already stored in a local `db.sqlite3` are not copied automatically.
- Retention, backups and a custom domain are pending decisions.
