# Backend test suite

Run from the repository root after `uv sync --locked`:

```bash
uv run --locked python manage.py test monitoring.tests --settings=config.test_settings
```

If the virtual environment is already installed, the equivalent command is:

```bash
.venv/bin/python manage.py test monitoring.tests --settings=config.test_settings
```

No running HTTP server, external credentials, AI model, or hardware is required. Django creates an in-memory SQLite test database, applies migrations, builds synthetic fixtures, and discards the database afterward. `config.test_settings` also isolates the cache and uses a fast test-only password hasher. Never use those settings to serve the application. Normal discovery (`python manage.py test`) still finds the whole suite and uses the configured database backend's test database.

## Run one area or one case

```bash
uv run --locked python manage.py test monitoring.tests.test_configuration --settings=config.test_settings -v 2
uv run --locked python manage.py test monitoring.tests.test_reports --settings=config.test_settings -v 2
uv run --locked python manage.py test monitoring.tests.test_sessions.SessionEndpointTests.test_history_invalid_filters_return_400 --settings=config.test_settings -v 2
```

Use `--failfast` to stop at the first failure. The process returns a nonzero exit status on failure, so the same command works in CI.

## Organization

| File | Coverage |
| --- | --- |
| `fixtures.py` | Shared synthetic participant/session/device/credential setup; no test-method inheritance |
| `test_api.py` | Batch persistence, idempotency, conflicts, rollback, authorization, delayed readings, counters, schema, configuration relationships |
| `test_ingestion_security.py` | Both ingestion routes: missing/invalid/revoked credentials, inactive devices, malformed JSON, unsupported media/methods, size/rate limits; batch structural limits |
| `test_configuration.py` | All six configuration resources: list/detail/create/PUT/PATCH/delete, staff restrictions, protected deletion, CSRF, invalid units/assignments/epochs |
| `test_sessions.py` | Session CRUD/access isolation, Basic authentication, history filters/pagination, observation ordering, latest readings, read-only routes |
| `test_vital_signs.py` | Five-metric adapter, duplicate/conflict behavior, missing and invalid scenarios |
| `test_dosimeter.py` | Dosimeter persistence, reset epochs, status/unit validation, durable offline replay |
| `test_reports.py` | Both data streams, three category tags, JSON/text, nulls, authorization, source separation, report bounds/limits and schema |
| `test_operations.py` | Health/readiness, simulated database outage, complete API schema inventory, Admin access and telemetry immutability |
| `test_models.py` | Model validation, UUIDs, uniqueness, relationships, timestamps, quality/value constraints |

These include unit tests of model behavior and endpoint integration tests using Django/DRF's in-process client. They exercise routing, serializers, authentication, permissions, and the test database; they do not open a network socket or verify a deployed HTTP server. Most human-authorized tests use `force_authenticate` to isolate endpoint behavior; dedicated tests also exercise real Basic authentication and session CSRF. Device requests use hashed credentials through the actual device authentication implementation.

## Endpoint review

All application API routes are inventoried in `test_operations.py` and compared with the generated OpenAPI schema. See [endpoint analysis](../../docs/endpoint-tests.md) for methods, access rules, fixes, and limitations.

## Database scope

The quick command validates SQLite behavior, not PostgreSQL concurrency. To run the same tests on PostgreSQL, configure the documented `DB_ENGINE=postgresql` and `DB_*` environment variables and run **without** `--settings=config.test_settings`:

```bash
uv run --locked python manage.py test monitoring.tests
```

Django needs permission to create a separate test database. This suite tests sequential retry idempotency and database constraints; simultaneous PostgreSQL ingestion races and load behavior remain unverified. Tests do not replace hardware/FRAM validation or clinical validation.
