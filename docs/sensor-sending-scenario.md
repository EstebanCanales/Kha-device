# Normal scenario: simulated watch sending readings

This example shows one monitoring session with the `vital_signs.py` simulator. It uses the same HTTP endpoint a future adapter could call. It does not connect to an ADI Study Watch or read Wavetool files.

## 1. Prepare the monitoring session

Create a participant and an **active** monitoring session in Django Admin. Give the session a readable identifier, such as `session-demo-001`, set `started_at` to a time before the simulator runs, leave `ended_at` empty, and add the human account that should be allowed to read the results under **Authorized users**.

Register the watch and its five simulated channels for that session, then issue one credential for the device:

```bash
uv run python manage.py setup_vital_signs session-demo-001
uv run python manage.py provision_device_token studywatch-sim-001
```

The credential command prints a `credential UUID:secret` pair once. Store it securely. A device credential may ingest telemetry for its own device; it cannot query session history.

## 2. Start the backend and simulator

In one terminal, start Django:

```bash
uv run python manage.py runserver
```

In another terminal, set the authorization header from the credential pair and run the simulator:

```bash
export TELEMETRY_AUTHORIZATION='Device CREDENTIAL_UUID:SECRET'
uv run python scripts/vital_signs.py \
  --url http://127.0.0.1:8000/api/v1/telemetry/vital-signs/ \
  --samples 10 --interval 1 --scenario baseline
```

The simulator sends ten separate HTTP `POST` requests, one per sample, approximately one second apart. Each request is one JSON `demo.v1` event. The backend authenticates the device, checks that it is assigned to a session at `measured_at`, validates the values, and stores one packet and five measurements.

For example, one request has this shape:

```json
{
  "schema_version": "demo.v1",
  "event_id": "run-id:0",
  "device_id": "studywatch-sim-001",
  "simulated": true,
  "sequence": 0,
  "measured_at": "2026-11-14T20:00:00+00:00",
  "scenario": "baseline",
  "quality": "synthetic",
  "metrics": {
    "heart_rate_bpm": 72.1,
    "pulse_rate_bpm": 72.1,
    "spo2_percent": 98.0,
    "respiratory_rate_per_min": 16.0,
    "skin_temperature_c": 33.42
  }
}
```

`run-id` is generated for each simulator run. The endpoint uses the device assignment and event time to find the monitoring session; this event field does not select a session. The response is `201` for a new stored event, `200` for an identical retry, `400` for invalid data, `401` for missing or invalid credentials, `403` when the device is not assigned, and `409` if an event ID is reused with different content.

The stored measurements are heart rate and pulse rate in `bpm`, SpO₂ in `%`, respiratory rate in `breaths/min`, and **skin temperature** in `degC`. This simulator sends derived scalar indicators only. It does not send raw PPG, ECG, EDA, bioimpedance, acceleration, steps, distance, or activity duration.

## 3. Read the session history

Use the session UUID printed by `seed_demo` or find the session in Admin. Query with the authorized human account and choose a source explicitly:

```bash
curl -u YOUR_USERNAME \
  'http://127.0.0.1:8000/api/v1/sessions/SESSION_UUID/measurements/?source=simulated'
```

The response is paginated and includes each value, unit, quality, sensor, measurement time, server receipt time, and source. The `/latest/` route returns the latest reading by sensor, metric, unit, and counter epoch. It reports the observation time and does not claim the reading is current.

## 4. Try signal loss and invalid values

Signal loss is represented as missing readings with `null`, not zero:

```bash
uv run python scripts/vital_signs.py \
  --url http://127.0.0.1:8000/api/v1/telemetry/vital-signs/ \
  --samples 9 --interval 1 --scenario signal-loss
```

The `invalid` scenario deliberately sends an SpO₂ value above 100 for some events. Those events receive a client error and are not stored. The simulator reports failed HTTP requests in its summary.

The simulator currently does not keep an offline queue or retry a failed request. Also, each run creates a new event ID, so starting the simulator again creates new events rather than replaying the previous run. A production sensor adapter will need to persist each event ID and payload until it receives a successful response.
