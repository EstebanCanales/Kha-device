#!/usr/bin/env python3
"""HTTP-only simulator for the Kha-device 01 profiles (CAD dosimeter and vital-signs device).

Every value is synthetic. Packet identities are derived from the seed, device, and
timestamp, so repeating a run resends the same packets and the backend answers with
duplicates instead of storing readings twice.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # lets the script import monitoring.demo_data

from monitoring.demo_data import CAD, VITALS, generate  # noqa: E402

BATCH = 100  # backend limit per request


def packet(args, device_id, at, readings):
    name = f"kha-sim:{args.seed}:{device_id}:{at.isoformat()}"
    return {
        "packet_id": str(uuid.uuid5(uuid.NAMESPACE_URL, name)), "device_id": device_id,
        "session_id": args.session, "observed_at": at.isoformat(), "source": "simulated", "readings": readings,
    }


def send(base_url, token, packets):
    """Send one batch, retrying temporary failures with the same packets and growing waits."""
    body = json.dumps({"schema_version": 1, "packets": packets}).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/v1/telemetry/batches/", data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Device " + token},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.load(response)
                print(f"HTTP {response.status}: inserted={result['inserted']} duplicates={result['duplicates']}")
                return
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise SystemExit(f"Ingestion failed: HTTP {error.code} {error.read()[:300]!r}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 3:
                raise SystemExit("Ingestion failed after temporary connection errors.") from error
        time.sleep(2**attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--session", default="session-kha-001")
    parser.add_argument("--epoch-high", required=True, help="epoch_high printed by setup_kha_devices")
    parser.add_argument("--epoch-low", required=True, help="epoch_low printed by setup_kha_devices")
    parser.add_argument("--minutes", type=int, default=60, help="History to generate, ending now")
    parser.add_argument("--step-seconds", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--scenario", choices=("baseline", "stress"), default="stress",
                        help="stress shifts the last 30%% of the window away from the early baseline")
    parser.add_argument("--dropout", type=float, default=0.02, help="Chance of a missing heart-rate reading")
    parser.add_argument("--start-at", help="Fixed ISO timestamp (with timezone) for the first sample")
    args = parser.parse_args()
    if not 1 <= args.minutes <= 600 or not 5 <= args.step_seconds <= 3600:
        parser.error("Use --minutes 1..600 and --step-seconds 5..3600.")
    vitals_token, cad_token = os.getenv("VITALS_DEVICE_TOKEN"), os.getenv("CAD_DEVICE_TOKEN")
    if not vitals_token or not cad_token:
        parser.error("Set VITALS_DEVICE_TOKEN and CAD_DEVICE_TOKEN in the environment.")

    if args.start_at:
        start = datetime.fromisoformat(args.start_at)
        if start.tzinfo is None:
            parser.error("--start-at needs a timezone.")
    else:
        start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=args.minutes)
    samples = args.minutes * 60 // args.step_seconds
    vitals, cad = [], []
    for at, vitals_readings, cad_readings in generate(
        start, samples, args.step_seconds, args.seed, args.scenario, args.dropout, args.epoch_high, args.epoch_low
    ):
        vitals.append(packet(args, VITALS, at, vitals_readings))
        cad.append(packet(args, CAD, at, cad_readings))

    for token, packets in ((vitals_token, vitals), (cad_token, cad)):
        for i in range(0, len(packets), BATCH):
            send(args.base_url, token, packets[i : i + BATCH])
    print(f"Sent {samples} samples per device, scenario={args.scenario}, first at {start.isoformat()}.")


if __name__ == "__main__":
    main()
