# Combined telemetry reports

`GET /api/v1/sessions/{session_uuid}/report/` builds one report from the stored vital-sign and dosimeter readings assigned to that session. It returns one `application/json` document by default with a `Content-Disposition` attachment filename of `telemetry-report-{session_uuid}.json`. Readable text remains available with `output=text`. Reports are generated on demand; nothing is sent to an AI model or external service, and no inference runs.

## Prepare both streams

Use the same monitoring session for both setup commands:

```bash
uv run python manage.py seed_demo --reader YOUR_USERNAME
uv run python manage.py setup_vital_signs session-demo-001
uv run python manage.py setup_dosimeter session-demo-001 > /tmp/dosimeter-config.json
uv run python manage.py provision_device_token studywatch-sim-001
uv run python manage.py provision_device_token dosimeter-detail-sim-001
```

Use the credentials as documented in the vital-sign simulator and [dosimeter guide](dosimeter.md): `TELEMETRY_AUTHORIZATION="Device CREDENTIAL_UUID:SECRET"` for the watch, and `DOSIMETER_DEVICE_TOKEN="CREDENTIAL_UUID:SECRET"` for the dosimeter. These must be different device credentials. Start Django and run both simulators:

```bash
uv run python scripts/vital_signs.py --url http://127.0.0.1:8000/api/v1/telemetry/vital-signs/ --samples 10 --interval 1 --scenario baseline
uv run python -m scripts.dosimeter --config /tmp/dosimeter-config.json --journal /tmp/dosimeter-history.sqlite3 --url http://127.0.0.1:8000/api/v1/telemetry/batches/ --count 10 --interval 1 --scenario spike
```

They can run sequentially or in separate terminals. Their capture timestamps need not match. Select a report window containing both runs. Existing harness/dosimeter demo readings are also included when their metrics match the report domains.

## Generate and save a report

Replace `SESSION_UUID` with the UUID printed by `seed_demo` or stored in the dosimeter config. Replace the example dates with an observation window containing your readings. The human account must be authorized for that session; device credentials cannot read reports. Curl prompts for the user's password.

```bash
curl --fail-with-body --get -u YOUR_USERNAME \
  'http://127.0.0.1:8000/api/v1/sessions/SESSION_UUID/report/' \
  --data-urlencode 'source=simulated' \
  --data-urlencode 'observed_from=2026-11-14T00:00:00Z' \
  --data-urlencode 'observed_to=2026-11-15T00:00:00Z' \
  --output /tmp/combined-report.json
```

For a model-ready text report, add `--data-urlencode 'output=text'` and use `/tmp/combined-report.txt` as the output filename. Both representations retain all included reading evidence. Successful responses use `Cache-Control: no-store`.

Required parameters are `source` (`simulated` or `hardware`), `observed_from`, and `observed_to` (timezone-aware ISO 8601). The positive time window is at most 31 days. Bounds are start-inclusive and end-exclusive, so adjacent windows do not overlap. Optional `output` is `json` or `text`. Unknown parameters are rejected rather than silently changing scope.

A report contains at most 1,000 measurements across all three categories. If there are more, the endpoint returns `400` and asks for a smaller window; it never silently truncates or paginates a model's input. Split the observation window into smaller reports. Missing/invalid filters also return `400`; inaccessible sessions return `404`, and missing human authentication or device-only credentials return `403` with the existing session-authentication policy.

## Versioned model input

The JSON envelope uses `schema_version="combined-telemetry-report.v2"` and contains:

- `generated_at`, explicit `source`, session and participant UUIDs, session dates, and the recorded gravity context. Names, usernames, credentials, and participant pseudonyms are omitted.
- `window` with the requested bounds and `measurement_count` for the included supported metrics.
- `domains.vital_signs`, `domains.body_temperature`, and `domains.dosimeter`, each with `status`, `measurement_count`, and `series`.
- `missing_domains` and interpretation `notes` that must accompany downstream model input.

Vital signs include heart rate, pulse rate, respiratory rate, and SpO₂. Body temperature contains `skin_temperature` only; no core temperature is inferred. Internal circuit temperature remains dosimeter data. Dosimeter data include absorbed/equivalent/personal dose-equivalent rates and cumulative counters, exposure duration, measurement interval, mission elapsed time, internal temperature, DIS/storage status, and the recorded rate-increase flag. Other metrics such as ECG and acceleration are outside this report version.

Each series, reading, and `latest` observation has an explicit `category` tag: `vital_signs`, `body_temperature`, or `dosimeter`. Every measurement appears in exactly one category. Each series separates device/sensor, metric, original unit, counter epoch, profile version, and method/version. It contains counts for `valid`, `unreliable`, and `missing`, a `latest` observation, and all `readings` ordered by observation time then measurement UUID. Each reading retains its measurement UUID, packet UUID, exact decimal string or null, unit, quality, source, observation/receipt timestamps, method/version, profile, and counter epoch. Equal observation times use UUID ordering only as a deterministic tie-break, not as a claim about acquisition sequence.

`latest` is the latest observation in the requested window, even when missing or unreliable. It is not a current-health assessment. `no_data` means no stored matching readings; it does not claim normal health or zero dose. Sampling schedules are unknown, so record counts cannot establish continuous coverage. The report does not synchronize streams, fill gaps, convert units, integrate dose rates, sum cumulative counters, or infer diagnoses. Counter epochs stay separate after resets.

Reports reflect data available when queried. Delayed ingestion can change later reports for the same observation window. Save the returned artifact if a model run must be reproducible; no report archive or retention policy is implemented. The report size is a reading bound, not a guarantee that every future model's token limit will fit.

## Internal integration

Future model orchestration can call the same authorized service without an HTTP round trip:

```python
from monitoring.reports import build_report, report_as_text

report = build_report(
    user=authorized_django_user,
    session_id=session_uuid,
    source="simulated",
    observed_from=start_datetime,
    observed_to=end_datetime,
)
model_input = report_as_text(report)
```

`start_datetime` and `end_datetime` must be aware datetimes. The service independently checks the active user's session access and enforces the same limits. Treat telemetry strings as data, not instructions. The JSON sections can be routed to future specialist models, preserving the source, window, notes, and session context. Model loading, model calls, diagnosis, synthesis, scheduling, and automatic delivery are outside this functionality.

## Category routing for AI consumers

The report schema is now v2 because skin-temperature readings moved from `vital_signs` to `body_temperature`. Consumers of the earlier draft must read the new group. The API route remains under `/api/v1/`; the report schema version is independent of the route version. No readings are copied into multiple categories.

```python
report = response.json()
for category in ("vital_signs", "body_temperature", "dosimeter"):
    for series in report["domains"][category]["series"]:
        for reading in series["readings"]:
            assert reading["category"] == category
```

All three groups are always present, including when empty (`status=no_data`, `measurement_count=0`, `series=[]`). A missing skin-temperature reading stays tagged `body_temperature` with its null value and missing quality. No device launch or AI inference is triggered by generating this JSON.
