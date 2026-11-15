# Endpoint analysis and test coverage

The application exposes 20 OpenAPI paths, two operational checks, and the Django Admin route hierarchy. `HEAD`/`OPTIONS` are supplied by the framework where supported. Configuration and session routes use internal UUIDs; ingestion uses the documented device/session/sensor identifiers.

| Route | Application methods | Access | Main behavior tested |
| --- | --- | --- | --- |
| `/api/v1/config/participants/` and `/{id}/` | List/create; retrieve/PUT/PATCH/delete | Staff | Full CRUD, authorization, protected deletion |
| `/api/v1/config/devices/` and `/{id}/` | List/create; retrieve/PUT/PATCH/delete | Staff | Full CRUD, authorization, referenced devices protected |
| `/api/v1/config/sensors/` and `/{id}/` | List/create; retrieve/PUT/PATCH/delete | Staff | Full CRUD, ownership/configuration relationships, protected deletion |
| `/api/v1/config/capabilities/` and `/{id}/` | List/create; retrieve/PUT/PATCH/delete | Staff | Full CRUD, invalid units rejected, used capability protected |
| `/api/v1/config/assignments/` and `/{id}/` | List/create; retrieve/PUT/PATCH/delete | Staff | Full CRUD, overlap rejected, historical references protected |
| `/api/v1/config/counter-epochs/` and `/{id}/` | List/create; retrieve/PUT/PATCH/delete | Staff | Full CRUD including partial updates, overlap/end validation, referenced epochs protected |
| `/api/v1/sessions/` and `/{id}/` | List/create; retrieve/PUT/PATCH/delete | Staff writes; assigned users read | Reader isolation, CRUD, protected deletion, Basic authentication |
| `/api/v1/sessions/{id}/measurements/` | GET | Assigned user or staff | Source/metric/sensor/time filters, stable order, pagination, invalid dates, no writes |
| `/api/v1/sessions/{id}/latest/` | GET | Assigned user or staff | Latest by observation time, delayed data, filters, no writes |
| `/api/v1/sessions/{id}/report/` | GET | Assigned user or staff | Combined JSON/text, vital/body-temperature/dosimeter tags, quality, units, epochs, bounded windows, no writes |
| `/api/v1/telemetry/batches/` | POST | Active device credential | Atomic persistence, duplicates/conflicts, device/session isolation, strict contract, null signals, size/rate limits |
| `/api/v1/telemetry/vital-signs/` | POST | Active device credential | Watch adapter, five readings, retries, invalid/missing scenarios, authentication, size/rate limits |
| `/api/v1/schema/` | GET | Public | All 20 API paths and device-authentication scheme |
| `/healthz/` | GET check | Public | Process response `200 {"status":"ok"}` |
| `/readyz/` | GET check | Public | Database available `200`; database failure `503` without exception details |
| `/admin/` and observation detail/delete routes | Django Admin | Active staff with model permissions | Login gating; stored measurements/packets cannot be changed or deleted even by a superuser |

Configuration CRUD status expectations: create `201`, reads/updates `200`, delete `204`, invalid input `400`, protected deletion `409`. Session/configuration permission failures return `403`; inaccessible session records/actions return `404`. Device-authentication failures return `401`; other-device/session submissions return `403`. Ingestion creates return `201`, identical retries `200`, changed-content retries `409`, oversized bodies `413`, and throttled requests `429` with `Retry-After`.

## Errors found and fixed

1. A well-shaped but impossible date such as `2026-02-30T00:00:00Z` caused an uncaught `ValueError` on history/latest queries. Both now return `400`. Regression tests retain both routes and malformed, timezone-free, reversed, and oversized ranges.
2. Counter-epoch PATCH requests omitting `ended_at` could trigger a DRF conditional-uniqueness `KeyError`. The serializer now delegates model-level constraint validation to its existing `full_clean()` path, which has the complete record. Tests cover successful partial updates, overlapping epochs, invalid ends, and unchanged stored state on failure.

## Current limits of the review

- The automated tests cover application routes and selected Admin security behavior, not every framework-generated Admin form or every possible input combination.
- The local suite uses SQLite by default. On 2026-11-15 the full suite and all migrations were also run against PostgreSQL 14 and passed; that run exercised the database constraints, not load or truly parallel clients. Throughput and hardware integrations are not established by these tests.
- History range limits apply when both optional bounds are supplied; latest currently scans matching rows before paginating. Configuration viewsets declare pagination but have no default page size, so their lists currently return all rows. These scalability behaviors were inspected and left unchanged by this testing task.
- Health/readiness are plain Django views and currently also accept methods other than GET; tests document the intended GET checks without introducing a routing change.
- Throttling uses the existing process-local cache. Tests isolate and exercise it; they do not establish multi-process limits.

Run instructions and individual test commands: [monitoring/tests/README.md](../monitoring/tests/README.md).


## Added after this review

These routes were added later and are covered by `monitoring/test_kha.py`, `monitoring/test_signup.py` and `monitoring/tests/test_nasa_radiation.py`:

| Route | Methods | Access | Main behavior tested |
| --- | --- | --- | --- |
| `/api/v1/sessions/{id}/overview/` | GET | Readers | One response with analysis, series and engine; downsampling; empty sessions; authorization and required `source` |
| `/api/v1/sessions/{id}/analysis/` | GET | Readers | Baseline shifts, dose counters per chamber, gaps, insufficient data |
| `/api/v1/sessions/{id}/summary/` | POST | Readers | Runs the summary module; `503` when the engine is unavailable; stores nothing |
| `/api/v1/sessions/{id}/radiation-context/` | GET | Readers | NASA DONKI events, caching, throttling, missing key |
| `/accounts/signup/` | GET, POST | Public while enabled | Account creation, validation, rate limit, `404` when disabled |
| `/app/` | GET | Signed-in account | Redirect to login when anonymous |

"Readers" are staff, accounts authorized for the session, and every signed-in account when `OPEN_READ_ACCESS` is on. The deployed site was also checked by hand over HTTPS behind the Railway proxy: health checks, login, sign-up, static files, and reading the demonstration session with a new account.
