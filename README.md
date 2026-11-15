# Kha-device backend

Django prototype for storing simulated physiological and dosimetry telemetry. The model is ready for a future sensor adapter, but no hardware profile or medical interpretation has been verified.

## Run locally

Python 3.12+ and [uv](https://docs.astral.sh/uv/) are required. SQLite is the default local database; PostgreSQL is supported through environment variables.

```bash
uv sync --locked
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

For PostgreSQL set `DB_ENGINE=postgresql` plus `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` before running migrations. In deployment also set `DJANGO_DEBUG=false`, a private `DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS`. See [.env.example](.env.example) for configuration names; the application reads environment variables, not `.env` files automatically. HTTPS is required outside local development. Do not apply migrations to a production database without a backup and review.

Admin is at `http://127.0.0.1:8000/admin/`. Staff can configure records there or via `/api/v1/config/`. Session users can read only sessions assigned to them. Device credentials only permit ingestion.

## HTTP demonstration

With the server running, create explicit synthetic profiles and authorize the user created above:

```bash
uv run python manage.py seed_demo --reader YOUR_USERNAME
uv run python manage.py provision_device_token harness-sim-001
uv run python manage.py provision_device_token dosimeter-sim-001
```

`seed_demo` prints `session_uuid`, `old_epoch`, `new_epoch`, and `reset_at`. Each token command prints one `credential UUID:secret` pair once. Store each token securely and set `HARNESS_DEVICE_TOKEN` and `DOSIMETER_DEVICE_TOKEN` in the environment. The verifier is hashed in the database. Revoke a credential in Admin, or issue a replacement with `--revoke-existing`.

Send real HTTP requests with the simulator:

```bash
python3 scripts/simulate_telemetry.py --new-epoch NEW_EPOCH_UUID --old-epoch OLD_EPOCH_UUID --reset-at RESET_AT --seed 7 --count 3 --interval-seconds 2 --delay-seconds 120 --duplicate --missing --counter-reset
```

The script uses the two environment tokens, sends through `/api/v1/telemetry/batches/`, and retries temporary failures with increasing waits while keeping the same packet IDs. `--duplicate` resends identical batches, `--missing` emits a null reading, and `--counter-reset` sends a delayed reading from the previous counter epoch. For identical results across separate runs, use the same `--seed` and an explicit `--start-at` timestamp within the demo session. All profiles and numbers are synthetic.

Consult the resulting history with the authorized human account (curl prompts for its password):

```bash
curl -u YOUR_USERNAME 'http://127.0.0.1:8000/api/v1/sessions/SESSION_UUID/measurements/?source=simulated'
```

An unauthenticated sender gets `401`:

```bash
curl -i -H 'Content-Type: application/json' -d '{}' 'http://127.0.0.1:8000/api/v1/telemetry/batches/'
```

## API surface

| Route | Access | Operation |
| --- | --- | --- |
| `/api/v1/config/participants/` | Staff | CRUD |
| `/api/v1/config/devices/` | Staff | CRUD |
| `/api/v1/config/sensors/` | Staff | CRUD |
| `/api/v1/config/capabilities/` | Staff | CRUD |
| `/api/v1/config/assignments/` | Staff | CRUD |
| `/api/v1/config/counter-epochs/` | Staff | CRUD |
| `/api/v1/sessions/` | Staff CRUD; assigned users read | Sessions |
| `/api/v1/sessions/{uuid}/measurements/` | Assigned users and staff | Paginated history |
| `/api/v1/sessions/{uuid}/latest/` | Assigned users and staff | Latest per sensor, metric, unit, and counter epoch |
| `/api/v1/telemetry/batches/` | Device credential | Atomic batch ingest |
| `/api/v1/schema/` | Public | OpenAPI schema |
| `/healthz/`, `/readyz/` | Public | Process and database checks |

Configuration mutations use Django session authentication with CSRF or HTTP Basic authentication. A protected configuration record cannot be deleted. Telemetry packets and measurements have no general update or delete endpoint. Both history routes require an explicit `source=simulated` or `source=hardware` query parameter.

## Checks

```bash
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py migrate
uv run python manage.py test
```

The local smoke test used SQLite; PostgreSQL constraints and concurrent retries still need verification on a running PostgreSQL server. See [telemetry contract](docs/telemetry-contract.md), [model notes](docs/models.md), and [decisions](docs/decisions.md).

## vital_signs simulator endpoint

`POST /api/v1/telemetry/vital-signs/` accepts the existing `demo.v1` events from `monitoring/sensors/vital_signs.py`. It stores five separate measurements per event: heart rate, pulse rate, SpO₂, respiratory rate, and **skin** temperature. This is a synthetic adapter, not a verified ADI watch protocol or Wavetool importer. Raw signals and activity outputs described for the watch are not emitted by this simulator.

Create a session (or use `seed_demo --reader YOUR_USERNAME`), then configure its simulated watch:

```bash
uv run python manage.py migrate
uv run python manage.py setup_vital_signs session-demo-001
uv run python manage.py provision_device_token studywatch-sim-001
```

Set `TELEMETRY_AUTHORIZATION` to `Device CREDENTIAL_UUID:SECRET` using the credential printed once by the command. Start Django with `uv run python manage.py runserver`, then send:

```bash
uv run python monitoring/sensors/vital_signs.py --url http://127.0.0.1:8000/api/v1/telemetry/vital-signs/ --samples 10 --interval 1 --scenario baseline
```

The endpoint resolves the session from the registered device assignment at `measured_at`. The random run ID inside `event_id` is not a monitoring-session identifier. HTTP 201 means stored, 200 means an identical retry, and 409 means the same event identity was reused with different readings. `signal-loss` stores nulls; `invalid` deliberately produces rejected events. A credential cannot send for another device or a hardware profile. Read results through the existing session history endpoint with `source=simulated`.

The simulator already performs HTTP sending when `--url` is provided; the endpoint receives and stores those messages. It does not launch a long-running simulator inside an HTTP request. Simulator runs generate new event identities; retries of an event must retain its original ID and body.

See [normal sensor sending scenario](docs/sensor-sending-scenario.md) for the session setup, request flow, and history query.

## Dedicated dosimeter

The new [dosimeter simulator and run guide](docs/dosimeter.md) records absorbed dose rate, cumulative absorbed dose with reset epochs, exposure history and increases, reading/mission timing, internal temperature, and synthetic DIS/storage status. It sends through the existing authenticated batch endpoint and keeps a durable local journal for offline replay. SQLite stands in for device storage; physical FRAM and DIS integration require hardware specifications.

## Combined reports for model input

`GET /api/v1/sessions/{uuid}/report/?source=simulated&observed_from=START&observed_to=END` combines stored vital-sign and dosimeter readings from the same session. It returns a single downloadable JSON document (`combined-telemetry-report.v2`) with `vital_signs`, `body_temperature`, and `dosimeter` categories. Every reading carries a `category` tag. Body temperature currently means skin temperature; the dosimeter’s internal temperature stays in the dosimeter category. Add `&output=text` for readable model input. Use timezone-aware dates and an authorized human account. Reports preserve quality, units, timestamps, and counter epochs, and explicitly identify missing domains. Limits: 31 days and 1,000 readings per report, with no silent truncation. See the [combined report guide](docs/combined-reports.md) for setup, export, and internal Python usage. This functionality generates reports only; it does not run AI models.

## Quick automated endpoint tests

All tests live in [`monitoring/tests/`](monitoring/tests/README.md). Run the isolated suite with no server or hardware:

```bash
uv run --locked python manage.py test monitoring.tests --settings=config.test_settings
```

This uses an in-memory SQLite database and a test-only fast password hasher. For one area, replace `monitoring.tests` with `monitoring.tests.test_reports`, `monitoring.tests.test_configuration`, or another module listed in the test guide. See [endpoint analysis and coverage](docs/endpoint-tests.md) for the full route inventory and limitations.
