# AGENTS.md — Astronaut Monitoring Backend

## Purpose and context

Act as the development agent for this Django backend. The system receives telemetry from a physiological monitoring harness and an active ionizing-radiation dosimeter worn by an astronaut. Required domains are cardiovascular, respiratory, blood oxygenation, temperature, physical activity, altered-gravity context, and radiation dose/exposure history.

This is an acquisition and query prototype. Hardware models, firmware, sampling rates, communication interfaces, and real message formats are not confirmed. Do not claim clinical validation, aerospace certification, or diagnostic capability.

## Mission

Implement a verifiable end-to-end flow: an authenticated simulator sends readings, the backend validates and stores them, and an authorized user queries the history.

Priorities:
1. Inspect and reuse the repository structure.
2. Configure Django, dependencies, environment variables, and the database.
3. Model participants, monitoring sessions, devices, sensors, packets, and measurements.
4. Implement a versioned ingestion contract at `/api/v1/`.
5. Protect ingestion and queries with authentication and authorization.
6. Support retries, delayed data, and disconnections without duplicate measurements.
7. Add simulation, tests, and reproducible documentation.

Do not implement frontend, firmware, diagnostics, medical alerts, AI, treatment recommendations, radiological-risk calculations, streaming, ECG processing, MQTT, queues, or distributed infrastructure without a concrete requirement.

### Extensions approved on 2026-11-14

The project owner explicitly asked for these, so they are no longer excluded above: a read-only operator dashboard at `/app/`, descriptive session analysis (`monitoring/analysis.py`), and the internal AI module (`ia/`). They stay inside the limits of this file: no diagnosis, no medical alerts or clinical thresholds, no radiological-risk calculation, no unit conversion, and simulated provenance stays explicit. See `docs/decisions.md`.

### Extensions approved on 2026-11-15

Also asked for by the project owner, and recorded in `docs/decisions.md`:

- **Hosting.** The prototype is deployed on Railway (backend, PostgreSQL, landing). Deploy only when asked.
- **Self-service sign-up** at `/accounts/signup/`, off outside development unless `ALLOW_SIGNUP` enables it.
- **Open read access** (`OPEN_READ_ACCESS`), off by default: every signed-in account reads every session. It is for demonstrations with simulated data and must be off before a session holds a real participant's readings. Writing stays staff-only.
- **Bilingual landing page**, English at `/` and Spanish at `/es/`, with the presentation video.

The limits of this file still apply to all of them. Start with `docs/architecture.md` for how the parts fit together and `docs/README.md` for the list of documents.

## Working rules

- Read the README, applicable instructions, dependency files, configuration, migrations, and tests before editing.
- Inspect Git status and preserve user changes. Do not overwrite unrelated work or use destructive operations.
- Adapt existing implementations; create the described foundation only when the repository is empty.
- Record provisional decisions and continue with simulation when hardware is unavailable.
- Do not invent hardware specifications, ports, credentials, units, commands, or test results.
- Do not deploy, publish, push, or modify external services unless explicitly requested.
- Explain progress and results in English. Keep code names, paths, commands, endpoints, and JSON keys unchanged.
- Prefer small functions, descriptive names, and comments explaining decisions. Put detailed specifications and decisions in `docs/`.

## Technical baseline

Use Python/Django, Django REST Framework, PostgreSQL, HTTP with JSON for local development, Django Admin, `/api/v1/`, OpenAPI, the existing test runner, and Ruff only when needed by a new project. Pin dependencies reproducibly and do not upgrade major versions for convenience.

Keep a modular monolith. If starting from scratch, use `config/`, `participants/`, `devices/`, and `telemetry/`. Keep models, serializers, ingestion services, views, queries, and the simulator separated. Ingestion logic must not depend on physical transport.

## Domain and data rules

Support proposed metrics such as `heart_rate`, `respiratory_rate`, `spo2`, `skin_temperature`, `core_temperature`, `ambient_temperature`, acceleration, angular velocity, dose rate, accumulated absorbed dose, and recorded exposure time. These are modeling options, not confirmed hardware capabilities.

Do not assume ECG, blood pressure, core temperature, respiratory volume, or automatically inferred gravity. Distinguish direct measurements from estimates and preserve method/version. Missing data, disconnected sensors, and poor signals must never become zero.

For dosimetry, preserve the exact quantity and original unit. Distinguish absorbed dose (Gy), equivalent dose/personal dose equivalent (Sv), dose rate, cumulative counters, interval increments, counter epochs, and resets. Do not convert counts or integrate rates without documented calibration and a validated model. Preserve instrument/protocol time and identify transmission gaps.

Implement `Participant`, `MonitoringSession`, `Device`, `Sensor`, `SessionDevice`, `TelemetryPacket`, and `Measurement`, with stable identifiers, foreign keys, indexes, and database constraints. Resolve participants through authorized sessions. Verify sensor ownership and time-bound session assignment. Store `observed_at` and server-generated `received_at` as UTC-aware timestamps. Preserve historical profile/calibration versions and distinguish `simulated` from hardware provenance.

Accepted readings are read-only in API and Admin. Use queryable columns for identity, metric, time, and value; use JSON only for bounded metadata or an authorized original payload.

## Ingestion contract

Implement `POST /api/v1/telemetry/batches/`. Each bounded batch contains packets with `packet_id`, `device_id`, `session_id`, `observed_at`, `source`, and readings containing `sensor_id`, `metric`, `value`, `unit`, and `quality`.

Use finite decimal strings for scalar values to preserve precision. Document identifier formats, vector representation, missing readings, technical limits, accepted units, and quality states such as `valid`, `unreliable`, and `missing`. All readings in one packet share `observed_at`; use separate packets for different capture times.

Validate schema, required fields, types, size, version, identifiers, permissions, sensor ownership, enabled metrics/units, finite values, and structural limits. Do not apply medical thresholds. Never silently replace `observed_at` with `received_at`.

Enforce uniqueness on `(device_id, packet_id)` in the database. Identical retries return duplicate confirmation without new readings; reused identities with different canonical content return `409 Conflict`. Batches are atomic for new packets, including under concurrency. Return per-packet status and inserted/duplicate totals. Document `400`, authentication/authorization errors, `409`, `413`, `429`, and temporary failures.

## Query API

Implement:

- `GET /api/v1/sessions/`
- `GET /api/v1/sessions/{id}/measurements/`
- `GET /api/v1/sessions/{id}/latest/`
- `GET /healthz/`
- `GET /readyz/`

Authorize every list, detail, route, and filter. Paginate, limit query ranges, and use stable ordering by time and identifier. Return value, unit, quality, provenance, and timestamps. Separate real and simulated data explicitly and do not call a recently received reading “current” without showing `observed_at`.

## Security and configuration

Distinguish device credentials from human accounts. Credentials must be individually revocable and rotatable; there must be no global shared device token. Use maintained authentication mechanisms, least privilege, secure secret storage, and CSRF protection for browser sessions.

Use environment variables, provide `.env.example` without real values, exclude `.env`, require `DEBUG=False`, allowed hosts, and correctly configured HTTPS for deployment. Limit body size, packets, readings, and request frequency. Do not log tokens, secrets, names, or complete physiological payloads. Use synthetic data only in fixtures, tests, and demonstrations. Treat retention as a pending decision.

## Simulation and tests

Provide a documented authenticated HTTP simulator that creates or uses demonstration participants, sessions, devices, and explicitly simulated sensor profiles. It must control seed, count, interval, duplicates, delays, signal loss, and dosimetry-counter resets. Do not present simulated profiles as verified real-instrument compatibility.

Test valid persistence/querying, missing/invalid/revoked credentials, device/session authorization, query isolation, atomic rollback, concurrent idempotent retries, content conflicts, incompatible units, unknown versions, non-finite values, delayed readings, missing signals, simulation provenance, and cumulative/reset counters. Verify database constraints and concurrency with PostgreSQL; state any limitation if another database is used.

Run, when available:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
```

Also run the configured linter and validate the OpenAPI schema and examples. Do not change tests to hide required behavior failures.

## Deliverables and acceptance

Provide a runnable Django project, reproducible dependencies, example configuration, models, migrations, indexes, constraints, authenticated ingestion and query APIs, Django Admin configuration, read-only telemetry, OpenAPI schema, simulator, end-to-end tests, `README.md`, `docs/telemetry-contract.md`, and `docs/decisions.md`.

The mission is complete when the README alone allows an evaluator to start the backend, register a demonstration session, send an authenticated batch through the real HTTP endpoint, query it, resend it without duplication, and verify rejection of an unauthorized sender. Report what was implemented, how it runs, what was checked, limitations, failures, and pending work. Do not claim hardware integration when only simulation was validated.

Pending hardware information includes sensor make/model/location, dosimeter quantities/calibration/units/counter references, real payloads and transport, sampling rates and volume, clock/disconnection/retry behavior, assignment and reset procedures, gravity context, deployment, authorized users, retention, and validated alert requirements. Treat these as unknowns until specified.

References: Codex `AGENTS.md` instructions, the project-version Django transaction documentation, Django REST Framework permissions, and IAEA radiation-protection question 23. These references do not define clinical requirements or certify space use.
