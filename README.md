# Kha-device 01

A prototype that receives telemetry from two wearable devices, stores it, compares each person with their own baseline, and shows the result in a dashboard. One device reads vital signs; the other is an active dosimeter for ionizing radiation.

**Everything here runs on simulated data.** No hardware model, firmware, sampling rate or message format has been confirmed. The project makes no diagnosis, raises no medical alert, computes no radiological risk, and is not validated for clinical or flight use.

| | |
| --- | --- |
| Landing page | <https://kha-device.up.railway.app> (English at `/`, Spanish at `/es/`) |
| Dashboard | <https://kha-device-app.up.railway.app/app/> (create an account from the login page) |
| Stack | Python 3.12+, Django 5.2, Django REST Framework, PostgreSQL (SQLite locally), Astro for the landing page |

New to the project? Read [docs/architecture.md](docs/architecture.md): it explains every part and how the pieces connect. The full list of documents is in [docs/README.md](docs/README.md).

## What is in this repository

| Path | What it is |
| --- | --- |
| `config/` | Django project: settings, URL routes, database configuration |
| `monitoring/` | The backend app: data model, ingestion, queries, analysis, dashboard, accounts |
| `ia/` | The summary module: a health specialist, a space specialist and a synthesis step |
| `scripts/` | Simulators that send data over real HTTP |
| `landing/` | The public landing page (Astro), deployed as its own static site |
| `docs/` | Contracts, decisions, guides |

## Run it locally

You need Python 3.12+ and [uv](https://docs.astral.sh/uv/). SQLite is used unless you configure PostgreSQL.

```bash
uv sync --locked
uv run python manage.py demo_kha      # migrates, creates the user "demo", registers both devices, loads 24 h of simulated data
uv run python manage.py runserver     # then open http://127.0.0.1:8000/app/
```

`demo_kha` prints the generated password once. It is safe to run again: it keeps the user and does not duplicate data. Its options:

| Option | Effect |
| --- | --- |
| `--more` | Add another window of data even if some already exists |
| `--minutes N` | Length of the history, ending now (default 1440, one day) |
| `--scenario baseline` | Keep every signal steady (the default, `stress`, shifts the last 30% so the analysis has something to report) |
| `--username NAME`, `--password PW` | Name and password of the demo account |
| `--no-user` | Load the session and data without creating an account; nothing secret is printed (used on the hosted deployment) |

Simulated devices report **one sample every 30 minutes**. That is a simulation choice, not a confirmed hardware rate.

To run the landing page too:

```bash
cd landing
bun install
bun dev                               # http://localhost:4321
```

## How the data flows

1. A device (today, a simulator) sends a batch of readings to `POST /api/v1/telemetry/batches/`, authenticated with its own credential.
2. The backend validates every reading (device, session, sensor, metric, unit, value, time) and stores the batch atomically. A repeated batch is recognised and not stored twice.
3. A signed-in person opens the dashboard, which asks for one `overview`: the stored series, a descriptive analysis against that person's own baseline, and which summary engine is active.
4. On request, the summary module turns the analysis into three short texts: health, space, and a synthesis.

Details, with the reasons behind each step, are in [docs/architecture.md](docs/architecture.md).

## Configuration

The application reads environment variables. It does not load `.env` by itself; pass a file with `uv run --env-file .env ...`. All names, with comments, are in [.env.example](.env.example).

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_DEBUG` | Development mode. Must be `false` in any deployment | `true` |
| `DJANGO_SECRET_KEY` | Signing key. Required when debug is off | development key |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names. Required when debug is off (the Railway domain is added automatically) | empty |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Extra HTTPS origins allowed to post forms, for a custom domain | empty |
| `DJANGO_BEHIND_PROXY` | Trust the proxy's `X-Forwarded-Proto` header. Only behind a proxy that ends TLS | `false` |
| `DATABASE_URL` | One PostgreSQL connection string. Takes precedence over `DB_*` | empty |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL by separate variables (`DB_ENGINE=postgresql`) | SQLite file |
| `DB_CONN_MAX_AGE` | Seconds a database connection is reused | `60` |
| `LANDING_URL` | Where signing out sends the browser | `http://localhost:4321/` |
| `ALLOW_SIGNUP` | Self-service account creation | on in debug, off otherwise |
| `SIGNUP_DEMO_SESSION` | Session identifier granted to new accounts and at login | empty |
| `OPEN_READ_ACCESS` | Every signed-in account reads every session | `false` |
| `IA_ENGINE` | Summary engine: `rules`, `ollama` or `huggingface` | `rules` |
| `RADIATION_API_KEY` | NASA DONKI key for space-weather context (`RADATION_API_KEY` is also accepted) | empty |
| `TELEMETRY_MAX_BODY_BYTES`, `TELEMETRY_FUTURE_SKEW_SECONDS` | Ingestion body limit and allowed clock skew into the future | `262144`, `300` |

For PostgreSQL, set `DATABASE_URL` (for example `postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require`) or the separate `DB_*` variables, then run `python manage.py migrate`. Only PostgreSQL URLs are accepted. The connection string is a secret: keep it in the environment or a git-ignored `.env`, never in the repository. Do not apply migrations to a database with real data without a backup.

## The dashboard

`/app/` is a single screen served by Django; it needs a signed-in account and uses only the `/api/v1/` routes.

- **Top bar:** session, simulated or hardware source, chart period (6 h, 12 h, 24 h), live state, pause, help.
- **Summary strip:** one plain-language status and the latest value of each signal with a small trend line.
- **Vital signs and dosimeter:** one chart per sensor. The green band is that person's usual range in this session; a dotted red line marks when a signal left it.
- **Analysis:** the three summary texts, in tabs.
- **NASA chip:** radiation-belt events for the week before the last reading, as environmental context only.

It refreshes every 15 seconds and can be paused. If the backend stops answering it says so, keeps the last data, and offers a retry. An account with no readable session sees an explanation instead of an empty screen.

## Accounts and access

There are two kinds of credential, and they never mix: **people** sign in with a Django account; **devices** send data with their own revocable credential, which permits ingestion and nothing else.

- **Sign-up:** `/accounts/signup/`, linked from the login page. `ALLOW_SIGNUP` switches it on or off. A new account is never staff.
- **Reading, by default:** an account reads only the sessions an administrator authorized it for (Django Admin, or the session API).
- **`SIGNUP_DEMO_SESSION`:** new accounts, and existing ones at their next login, are authorized for that one demonstration session.
- **`OPEN_READ_ACCESS=true`:** every signed-in account reads every session. It is for demonstrations with simulated data and must be turned off before a session holds a real participant's readings.
- **Writing:** creating, changing and configuring sessions, devices and sensors is staff-only in every mode.
- **Rate limit:** 10 sign-up attempts per client address per hour, then HTTP 429. The counter lives in each worker's memory.
- **Not built yet:** email verification and password reset, pending the choice of a mail service.

## API surface

| Route | Access | Operation |
| --- | --- | --- |
| `/api/v1/telemetry/batches/` | Device credential | `POST`: atomic batch ingest |
| `/api/v1/telemetry/vital-signs/` | Device credential | `POST`: adapter for the `vital_signs.py` simulator |
| `/api/v1/sessions/` | Readers; staff write | Sessions the account may read |
| `/api/v1/sessions/{uuid}/measurements/` | Readers | Paginated history |
| `/api/v1/sessions/{uuid}/latest/` | Readers | Latest reading per sensor, metric, unit and counter epoch |
| `/api/v1/sessions/{uuid}/overview/` | Readers | Analysis, per-sensor series and summary engine in one response |
| `/api/v1/sessions/{uuid}/analysis/` | Readers | Baseline changes, dose counters, gaps |
| `/api/v1/sessions/{uuid}/summary/` | Readers | `POST`: run the summary module; stores nothing |
| `/api/v1/sessions/{uuid}/report/` | Readers | Combined vital-signs and dosimeter report, JSON or text |
| `/api/v1/sessions/{uuid}/radiation-context/` | Readers | NASA DONKI radiation-belt events for a date range |
| `/api/v1/config/{participants,devices,sensors,capabilities,assignments,counter-epochs}/` | Staff | Configuration CRUD |
| `/api/v1/schema/` | Public | OpenAPI schema |
| `/healthz/`, `/readyz/` | Public | Process and database checks |
| `/app/`, `/accounts/login/`, `/accounts/signup/`, `/admin/` | Browser | Dashboard, sign-in, sign-up, Django Admin |

"Readers" means staff plus the accounts allowed by the rules in the previous section. Every query that returns readings requires `source=simulated` or `source=hardware`, so the two are never mixed. Stored packets and measurements have no update or delete endpoint. The exact formats, limits and error codes are in [docs/telemetry-contract.md](docs/telemetry-contract.md).

## Sending data over HTTP

`demo_kha` writes straight to the database. To exercise the real HTTP endpoint with the same two devices:

```bash
uv run python manage.py createsuperuser
uv run python manage.py setup_kha_devices --reader YOUR_USERNAME     # prints session_uuid, epoch_high, epoch_low
export VITALS_DEVICE_TOKEN="$(uv run python manage.py provision_device_token kha-vitals-sim-001 | tail -1)"
export CAD_DEVICE_TOKEN="$(uv run python manage.py provision_device_token cad-sim-001 | tail -1)"
uv run python manage.py runserver
python3 scripts/simulate_kha.py --epoch-high EPOCH_HIGH --epoch-low EPOCH_LOW
```

Each token is printed once and stored only as a hash; revoke it in Admin or issue a replacement with `--revoke-existing`. Packet identities derive from the seed, the device and the timestamp, so running the simulator again reports duplicates instead of storing readings twice. An unauthenticated sender gets `401`:

```bash
curl -i -H 'Content-Type: application/json' -d '{}' 'http://127.0.0.1:8000/api/v1/telemetry/batches/'
```

The two devices are the Crew Active Dosimeter (two DIS chambers and a TMP117 for internal temperature) and the vital-signs device (MAX86178 for pulse, SpO₂ and respiratory rate; MAX30205 for skin temperature). Part numbers come from the project notes; the profiles are simulated.

Earlier simulators remain available, each with its own guide:

| Simulator | What it shows | Guide |
| --- | --- | --- |
| `scripts/simulate_telemetry.py` with `seed_demo` | Duplicates, delays, missing readings and a counter reset through the batch endpoint | the commands below |
| `scripts/vital_signs.py` | A watch-style adapter posting to `/api/v1/telemetry/vital-signs/` | [docs/sensor-sending-scenario.md](docs/sensor-sending-scenario.md) |
| `scripts/dosimeter.py` | A dedicated dosimeter with a local journal for offline replay | [docs/dosimeter.md](docs/dosimeter.md) |

The first one uses its own synthetic profiles (`harness-sim-001`, `dosimeter-sim-001`):

```bash
uv run python manage.py seed_demo --reader YOUR_USERNAME            # prints session_uuid, old_epoch, new_epoch, reset_at
uv run python manage.py provision_device_token harness-sim-001      # set HARNESS_DEVICE_TOKEN to the printed value
uv run python manage.py provision_device_token dosimeter-sim-001    # set DOSIMETER_DEVICE_TOKEN to the printed value
python3 scripts/simulate_telemetry.py --new-epoch NEW_EPOCH_UUID --old-epoch OLD_EPOCH_UUID --reset-at RESET_AT \
  --seed 7 --count 3 --interval-seconds 2 --delay-seconds 120 --duplicate --missing --counter-reset
curl -u YOUR_USERNAME 'http://127.0.0.1:8000/api/v1/sessions/SESSION_UUID/measurements/?source=simulated'
```

`--duplicate` resends identical batches, `--missing` sends a null reading, and `--counter-reset` sends a delayed reading from the previous counter epoch. Temporary failures are retried with the same packet identities.

## Analysis and summary

**Analysis** (`monitoring/analysis.py`) is descriptive statistics computed when asked; nothing is stored. For heart rate, SpO₂, respiratory rate and skin temperature it compares the latest readings with the same person's early readings in the same session, using the median and the median absolute deviation, and flags a change at 3 deviations. For each dosimeter chamber it reports the latest cumulative dose and the recent rate against the early rate. It needs at least 20 readings. The thresholds are provisional engineering choices, not medical or radiological limits.

**Summary** (`ia/`) runs a health specialist, a space specialist and a synthesis step over that analysis. `IA_ENGINE` chooses how:

- `rules` (default): fixed templates, no language model. This is what the hosted deployment uses.
- `ollama`: three models served by a local [Ollama](https://ollama.com), prepared once with `ia/ollama/setup.sh`.
- `huggingface`: the same models through transformers, after `uv sync --extra ia`.

The counts shown first in every summary are computed from the readings, never by a model. Text written by a model is shown separately and labelled as possibly wrong, and sentences citing figures that are not in the readings are discarded. See [ia/README.md](ia/README.md).

**NASA context.** With `RADIATION_API_KEY` set, the space specialist and the dashboard also receive NASA DONKI radiation-belt events. They are environmental events, never a personal dose. See [docs/dosimeter.md](docs/dosimeter.md#nasa-radiation-belt-context).

**Combined report.** `GET /api/v1/sessions/{uuid}/report/` returns one document with vital signs, body temperature and dosimeter readings for a time window, as JSON or text, for use as model input. See [docs/combined-reports.md](docs/combined-reports.md).

## Checks

```bash
uv run ruff check .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test          # 148 tests, no server or hardware needed
cd landing && bun run build
```

The suite runs on SQLite by default. Migrations and the whole suite were also run against PostgreSQL 14; set `DATABASE_URL` to a test server to repeat that. The test guide is [monitoring/tests/README.md](monitoring/tests/README.md).

## Hosting

The prototype runs on Railway as three services: the Django backend (gunicorn and WhiteNoise), a PostgreSQL database, and the static landing page. Setup, variables and deploy commands are in [docs/deploy-railway.md](docs/deploy-railway.md). On Railway the summary uses the `rules` engine, because local language models do not run there.

## Limits and pending work

- **Simulation only.** Nothing has been integrated with a real instrument.
- **Not medical.** No diagnosis, alert, treatment guidance or radiological-risk calculation.
- **Pending from hardware:** sensor models and placement, dosimeter quantities and calibration, real payloads and transport, sampling rates, clock and disconnection behaviour, gravity context.
- **Pending decisions:** data retention, backups, a custom domain, email verification and password reset.
- **Per-process state:** the ingestion and sign-up rate limits and the NASA cache live in each worker's memory; several workers need a shared cache.
- **Summaries run inside the request.** With real models that can take minutes; a real deployment would need a background job.

The reasoning behind these choices is recorded in [docs/decisions.md](docs/decisions.md).
