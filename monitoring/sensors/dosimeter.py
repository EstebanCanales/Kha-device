"""Synthetic dosimeter with a durable desktop journal, NOT a FRAM/DIS driver.

Run with python -m monitoring.sensors.dosimeter --help.
"""

import argparse
import json
import os
import random
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from monitoring.dosimeter_profile import CHANNELS, PROFILE_VERSION


def instant(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("Timestamps require a timezone.")
    return parsed.astimezone(timezone.utc)


def seconds(delta):
    return format(Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / 1000000, "f")


def make_sample(config, observed_at, previous=None, *, seed=7, scenario="baseline"):
    """Counter and rate are independent synthetic fixtures, never a calibrated conversion."""
    mission_start = instant(config["mission_started_at"])
    if observed_at.utcoffset() is None or observed_at < mission_start:
        raise ValueError("Reading must have a timezone and follow mission start.")
    if previous and observed_at <= instant(previous["observed_at"]):
        raise ValueError("New captures must follow the journal's last timestamp.")
    epoch = next((item for item in config["epochs"] if instant(item["started_at"]) <= observed_at and
                  (not item["ended_at"] or observed_at < instant(item["ended_at"]))), None)
    if epoch is None:
        raise ValueError("Reading falls outside configured counter epochs.")
    sequence = previous["sequence"] + 1 if previous else 0
    rng = random.Random(f"{seed}:{sequence}")
    missing = scenario == "signal-loss" and sequence % 3 == 1
    spike = scenario == "spike" and sequence % 6 in (2, 3)
    rate = Decimal(rng.randrange(10, 20)) / 1000 + (Decimal("0.2") if spike else 0)
    same_epoch = previous and previous["epoch"] == epoch["id"]
    total = Decimal(previous["counter"]) if same_epoch else Decimal("0")
    # Independent synthetic counter increments do not integrate a dose rate.
    total += Decimal(rng.randrange(1, 5)) / 1000
    last_rate = previous.get("rate") if previous else None
    increase = None if missing or last_rate is None else str(int(rate > Decimal(last_rate)))
    monitoring_start = instant(previous["monitoring_started_at"]) if previous else observed_at
    values = {
        "absorbed_dose_rate": None if missing else format(rate, "f"),
        "absorbed_dose_cumulative": None if missing else format(total, "f"),
        "exposure_duration": seconds(observed_at - monitoring_start),
        "measurement_interval": seconds(observed_at - instant(previous["observed_at"])) if previous else None,
        "mission_elapsed_time": seconds(observed_at - mission_start),
        "internal_temperature": format(Decimal(rng.randrange(2400, 2700)) / 100, "f"),
        "dis_chamber_status": "2" if missing else "1",
        "storage_status": "1",
        "dose_rate_increase": increase,
    }
    readings = []
    for metric, unit in CHANNELS.items():
        reading = {
            "sensor_id": f"{config['device_id']}-{metric}", "metric": metric, "unit": unit,
            "value": values[metric], "quality": "missing" if values[metric] is None else "valid",
            "method": "synthetic-fixture", "method_version": PROFILE_VERSION,
        }
        if metric == "absorbed_dose_cumulative":
            reading["counter_epoch"] = epoch["id"]
        readings.append(reading)
    packet = {
        "packet_id": str(uuid.uuid4()), "device_id": config["device_id"],
        "session_id": config["session_id"], "observed_at": observed_at.isoformat(),
        "source": "simulated", "readings": readings,
    }
    state = {
        "sequence": sequence, "observed_at": observed_at.isoformat(), "epoch": epoch["id"],
        "counter": format(total, "f"), "rate": None if missing else format(rate, "f"),
        "monitoring_started_at": monitoring_start.isoformat(),
    }
    return packet, state


class Journal:
    """SQLite stand-in for future FRAM storage; keep records after acknowledgment."""

    def __init__(self, path, config):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS configuration (body TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS samples (sequence INTEGER PRIMARY KEY, body TEXT NOT NULL, state TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0)")
        canonical = json.dumps(config, sort_keys=True)
        existing = self.db.execute("SELECT body FROM configuration").fetchone()
        if existing and existing[0] != canonical:
            self.db.close()
            raise ValueError("Journal belongs to a different configuration; use a separate journal.")
        if not existing:
            self.db.execute("INSERT INTO configuration VALUES (?)", (canonical,))
        self.db.commit()

    def last_state(self):
        row = self.db.execute("SELECT state FROM samples ORDER BY sequence DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def append(self, packet, state):
        with self.db:
            self.db.execute("INSERT INTO samples (sequence, body, state) VALUES (?, ?, ?)",
                            (state["sequence"], json.dumps(packet), json.dumps(state)))

    def replay(self, url, token, *, duplicate=False, sender=None):
        sender = sender or send
        for sequence, body in self.db.execute("SELECT sequence, body FROM samples WHERE sent=0 ORDER BY sequence"):
            packet = json.loads(body)
            sender(url, token, packet)
            if duplicate:
                sender(url, token, packet)
            with self.db:
                self.db.execute("UPDATE samples SET sent=1 WHERE sequence=?", (sequence,))

    def close(self):
        self.db.close()


def send(url, token, packet):
    request = urllib.request.Request(url, data=json.dumps({"schema_version": 1, "packets": [packet]}).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": f"Device {token}"}, method="POST")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.load(response)
                if response.status not in (200, 201) or result.get("inserted", 0) + result.get("duplicates", 0) != 1:
                    raise ValueError("Unexpected ingestion acknowledgment; record remains pending.")
                return
        except urllib.error.HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise ValueError(f"Ingestion rejected (HTTP {error.code}); records remain pending.") from None
        except (urllib.error.URLError, TimeoutError):
            pass
        if attempt < 3:
            time.sleep(2 ** attempt)
    raise ValueError("Temporary delivery failure; records remain pending for replay.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="JSON from setup_dosimeter")
    parser.add_argument("--journal", required=True, help="Local SQLite history; not real FRAM")
    parser.add_argument("--url", help="Full /api/v1/telemetry/batches/ URL; omit to capture offline")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--interval", type=int, default=1, help="Capture interval in seconds")
    parser.add_argument("--delay-seconds", type=int, default=0)
    parser.add_argument("--start-at", help="Capture start with timezone; default now minus delay")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--scenario", choices=["baseline", "spike", "signal-loss"], default="baseline")
    parser.add_argument("--duplicate", action="store_true")
    parser.add_argument("--replay-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.count <= 10000 or not 1 <= args.interval <= 86400 or args.delay_seconds < 0:
        parser.error("Use count 1..10000, interval 1..86400 seconds, and nonnegative delay.")
    token = os.getenv("DOSIMETER_DEVICE_TOKEN")
    if args.url and not token:
        parser.error("Set DOSIMETER_DEVICE_TOKEN before sending.")
    if args.replay_only and not args.url:
        parser.error("--replay-only requires --url.")
    journal = None
    try:
        with open(args.config) as file:
            config = json.load(file)
        if config["profile_version"] != PROFILE_VERSION:
            raise ValueError("Unsupported simulator profile.")
        journal = Journal(args.journal, config)
        if not args.replay_only:
            start = instant(args.start_at) if args.start_at else datetime.now(timezone.utc) - timedelta(seconds=args.delay_seconds)
            for index in range(args.count):
                packet, state = make_sample(config, start + timedelta(seconds=index * args.interval), journal.last_state(), seed=args.seed, scenario=args.scenario)
                journal.append(packet, state)
                if args.url:
                    try:
                        journal.replay(args.url, token, duplicate=args.duplicate)
                    except ValueError as error:
                        print(str(error))
                if index + 1 < args.count:
                    time.sleep(args.interval)
        else:
            journal.replay(args.url, token, duplicate=args.duplicate)
        pending = journal.db.execute("SELECT COUNT(*) FROM samples WHERE sent=0").fetchone()[0]
        print(f"Pending records: {pending}. History retained in local SQLite journal (not FRAM).")
        if args.url and pending:
            raise ValueError("Delivery incomplete; use --replay-only after resolving the connection or credentials.")
    except (ValueError, KeyError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"{error}\n")
    finally:
        if journal:
            journal.close()


if __name__ == "__main__":
    main()
