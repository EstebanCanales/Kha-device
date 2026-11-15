# Dedicated dosimeter simulator

This Python simulator implements the requested acquisition workflow against the existing authenticated batch API. It does not operate physical DIS chambers or FRAM. Hardware model, controller, calibration, chamber count, FRAM interface/capacity, clock, and vendor protocol remain unknown.

## Values recorded

| Requirement | Stored metric / behavior |
| --- | --- |
| Periodic absorbed dose rate | `absorbed_dose_rate`, decimal string in `uGy/h` |
| Cumulative absorbed dose | `absorbed_dose_cumulative`, `uGy`, with a registered counter epoch |
| Chronological exposure history | Local SQLite journal plus authorized backend history, including `observed_at` and `received_at` |
| Exposure increases | `dose_rate_increase`: `1` when the rate exceeds the immediately preceding valid reading; `0` otherwise; null at startup or across signal loss |
| Recorded monitoring duration | `exposure_duration`, seconds since the first journal capture |
| Reading interval | `measurement_interval`, seconds since the preceding capture; null on the first reading |
| Mission duration so far | `mission_elapsed_time`, seconds since the configured session start |
| Internal circuit temperature | `internal_temperature`, `degC` |
| DIS chamber state | `dis_chamber_status`, synthetic aggregate status, not an assumed chamber count |
| Storage state | `storage_status`, synthetic fixture status; actual journal write failures stop acquisition |

Status codes for this prototype are `0=unknown`, `1=ok`, `2=fault`, unit `code`. These are application codes, not vendor protocol codes. Missing status uses null and `quality=missing`. The increase flag uses dimensionless unit `1`; it describes a comparison, not a hazard threshold or medical alert. Consecutive timestamps with an increase flag identify intervals with rising recorded rates. Timing measures elapsed capture time, not time above a radiation threshold. Pauses in capture remain visible as larger intervals; there is no inferred dose during a gap.

The API also accepts `uGy/min` and `mGy/h` for absorbed dose rate and `uGy`, `mGy`, `Gy` for cumulative absorbed dose, provided the exact unit is enabled for the sensor. ASCII `u` represents the micro prefix. Original values and units are preserved. The simulator emits only `uGy/h` and `uGy`. Dose and rate fixtures are independent synthetic values: no counts conversion or rate integration is performed. A reset starts a separate counter epoch; cumulative samples and epochs must never be added to obtain a mission total. Before first capture there is no simulated measurement history.

## Run

Follow the README to migrate, create a human reader, seed a session, and start Django. Then:

```bash
uv run python manage.py setup_dosimeter session-demo-001 > /tmp/dosimeter-config.json
uv run python manage.py provision_device_token dosimeter-detail-sim-001
```

Set `DOSIMETER_DEVICE_TOKEN` to the printed `credential UUID:secret` pair through your environment. No credentials are stored in the configuration or journal.

```bash
uv run python -m scripts.dosimeter \
  --config /tmp/dosimeter-config.json --journal /tmp/dosimeter-history.sqlite3 \
  --url http://127.0.0.1:8000/api/v1/telemetry/batches/ \
  --count 10 --interval 1 --seed 7 --scenario spike --duplicate
```

Every capture is committed locally before HTTP delivery. A successful backend insert or duplicate acknowledgment marks the record sent; the original remains in the journal. Retries retain exact packet IDs and bodies. Temporary network/server failures receive bounded retries. Capture continues with pending records after delivery errors, and the process exits unsuccessfully if delivery remains incomplete. Network retries can delay the capture loop; timestamps represent the synthetic scheduled timeline, not precision hardware acquisition.

Omit `--url` to capture offline. Later replay pending records, including after a process restart:

```bash
uv run python -m scripts.dosimeter \
  --config /tmp/dosimeter-config.json --journal /tmp/dosimeter-history.sqlite3 \
  --url http://127.0.0.1:8000/api/v1/telemetry/batches/ --replay-only
```

Use `--scenario signal-loss` for periodic missing dose/rate readings and a synthetic chamber fault. `--delay-seconds 120` records a delayed timeline; `--start-at` supplies an explicit timezone-aware timestamp. Values are reproducible for a fixed seed and sequence; fresh captures get fresh UUIDs. Replaying a journal is the mechanism for identical retries. Continue a mission with the same journal to preserve the counter and monitoring start. A new journal begins a new synthetic fixture baseline and must not be treated as continuation of a previously recorded counter.

To demonstrate a counter reset, configure a **fresh** session/profile using `setup_dosimeter SESSION --reset-at TIMESTAMP`, with a timezone-aware timestamp strictly inside that session. Capture a timeline crossing that timestamp using `--start-at`. The setup command refuses to rewrite existing epochs. Counter resets preserve mission and monitoring time and start a new dose reference. Reuse the same setup arguments when regenerating configuration.

Read history using `session_uuid` from the JSON configuration:

```bash
curl -u YOUR_USERNAME 'http://127.0.0.1:8000/api/v1/sessions/SESSION_UUID/measurements/?source=simulated&metric=absorbed_dose_rate'
curl -u YOUR_USERNAME 'http://127.0.0.1:8000/api/v1/sessions/SESSION_UUID/measurements/?source=simulated&metric=absorbed_dose_cumulative'
```

Omit `metric` for all readings; follow pagination links. The session identifies the authorized participant. Existing endpoint authentication, session isolation, validation, atomicity, and duplicate/conflict semantics apply.

## Hardware work still needed

Replace the synthetic acquisition and desktop journal with documented hardware adapters once the actual controller, DIS dosimeter protocol, calibration/quantity, FRAM model/bus/address/capacity, clock, and power-loss behavior are supplied. The desktop journal is not a FRAM emulator and does not validate wear, capacity, bus timing, power-loss recovery, or instrument compatibility. It is single-process and has no retention/deletion policy. No physical dosimeter, space environment, clinical use, or PostgreSQL concurrency is validated by this simulator.
