#!/usr/bin/env python3
"""HTTP-only telemetry client for the explicitly simulated demo profiles."""

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone


def reading(sensor_id, metric, value, unit, **extra):
    return {"sensor_id": sensor_id, "metric": metric, "value": value, "unit": unit, "quality": "missing" if value is None else "valid", **extra}


def packet(device_id, observed_at, readings, rng):
    return {
        "packet_id": str(uuid.UUID(int=rng.getrandbits(128), version=4)), "device_id": device_id,
        "session_id": "session-demo-001", "observed_at": observed_at.isoformat(),
        "source": "simulated", "readings": readings,
    }


def send_batch(base_url, token, packets):
    body = json.dumps({"schema_version": 1, "packets": packets}).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/v1/telemetry/batches/", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Device " + token},
        method="POST",
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.load(response)
                print(f"HTTP {response.status}: inserted={result['inserted']} duplicates={result['duplicates']}")
                return
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise SystemExit(f"Ingestion failed: HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 3:
                raise SystemExit("Ingestion failed after temporary connection errors.") from error
        time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=2)
    parser.add_argument("--delay-seconds", type=int, default=120)
    parser.add_argument("--start-at", help="Fixed ISO timestamp for reproducible packet IDs and times")
    parser.add_argument("--new-epoch", required=True, help="UUID printed by seed_demo")
    parser.add_argument("--old-epoch", help="UUID printed by seed_demo, needed with --counter-reset")
    parser.add_argument("--reset-at", help="ISO timestamp printed by seed_demo, needed with --counter-reset")
    parser.add_argument("--duplicate", action="store_true")
    parser.add_argument("--missing", action="store_true")
    parser.add_argument("--counter-reset", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.count <= 50 or args.interval_seconds < 0 or args.count * args.interval_seconds >= 86400 or not 0 <= args.delay_seconds < 86400:
        parser.error("Use count 1..50 and keep the generated interval and delay below one day.")
    if args.counter_reset and (not args.old_epoch or not args.reset_at):
        parser.error("--counter-reset requires --old-epoch and --reset-at.")
    harness_token = os.getenv("HARNESS_DEVICE_TOKEN")
    dosimeter_token = os.getenv("DOSIMETER_DEVICE_TOKEN")
    if not harness_token or not dosimeter_token:
        parser.error("Set HARNESS_DEVICE_TOKEN and DOSIMETER_DEVICE_TOKEN in the environment.")

    rng = random.Random(args.seed)
    if args.start_at:
        try:
            start = datetime.fromisoformat(args.start_at)
        except ValueError:
            parser.error("--start-at must be an ISO 8601 timestamp with timezone.")
        if start.tzinfo is None or start.utcoffset() is None:
            parser.error("--start-at needs a timezone.")
    else:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        start = now - timedelta(seconds=args.count * args.interval_seconds + 1)
    harness_packets = []
    dosimeter_packets = []
    for index in range(args.count):
        observed_at = start + timedelta(seconds=index * args.interval_seconds)
        hr = None if args.missing and index == args.count - 1 else str(70 + rng.randrange(20))
        harness_packets.append(packet("harness-sim-001", observed_at, [
            reading("hr-sim-001", "heart_rate", hr, "bpm"),
            reading("rr-sim-001", "respiratory_rate", str(12 + rng.randrange(6)), "breaths/min"),
            reading("spo2-sim-001", "spo2", str(95 + rng.randrange(5)), "%"),
            reading("skin-temp-sim-001", "skin_temperature", f"{32 + rng.random():.6f}", "degC"),
            reading("accel-x-sim-001", "acceleration_x", f"{rng.uniform(-2, 2):.6f}", "m/s2"),
            reading("accel-y-sim-001", "acceleration_y", f"{rng.uniform(-2, 2):.6f}", "m/s2"),
            reading("accel-z-sim-001", "acceleration_z", f"{rng.uniform(-2, 2):.6f}", "m/s2"),
        ], rng))
        dosimeter_packets.append(packet("dosimeter-sim-001", observed_at, [
            reading("dose-rate-sim-001", "absorbed_dose_rate", f"{0.01 + rng.random() / 100:.6f}", "uGy/h"),
            reading("dose-total-sim-001", "absorbed_dose_cumulative", str((index + 1) / 100), "uGy", counter_epoch=args.new_epoch),
            reading("exposure-sim-001", "exposure_duration", str(index * args.interval_seconds), "s"),
        ], rng))

    send_batch(args.base_url, harness_token, harness_packets)
    send_batch(args.base_url, dosimeter_token, dosimeter_packets)
    if args.duplicate:
        send_batch(args.base_url, harness_token, harness_packets)
        send_batch(args.base_url, dosimeter_token, dosimeter_packets)
    if args.delay_seconds:
        late_at = start - timedelta(seconds=args.delay_seconds)
        send_batch(args.base_url, harness_token, [packet("harness-sim-001", late_at, [
            reading("hr-sim-001", "heart_rate", "75", "bpm")
        ], rng)])
    if args.counter_reset:
        reset_at = datetime.fromisoformat(args.reset_at.replace("Z", "+00:00"))
        old_at = reset_at - timedelta(seconds=1)
        send_batch(args.base_url, dosimeter_token, [packet("dosimeter-sim-001", old_at, [
            reading("dose-total-sim-001", "absorbed_dose_cumulative", "3.0", "uGy", counter_epoch=args.old_epoch)
        ], rng)])


if __name__ == "__main__":
    main()
