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

The script uses the two environment tokens, sends through `/api/v1/telemetry/batches/`, and retries temporary failures with increasing waits while keeping the same packet IDs. `--duplicate` resends identical batches, `--missing` emits a null reading, and `--counter-reset` sends a delayed reading from the previous counter epoch. All profiles and numbers are synthetic.

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
