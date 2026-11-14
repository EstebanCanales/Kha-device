
import argparse
import json
import math
import os
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# Keep the documented direct-script invocation working as well as module imports.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from monitoring.body_temperature import MAX30205Simulator


def make_event(index, count, scenario, rng, start, session_id, temperature_sensor=None):
    measured_at = start + timedelta(seconds=index)
    hr = 72 + 2 * math.sin(index / 5) + rng.uniform(-0.5, 0.5)
    rr = 16 + 0.5 * math.sin(index / 7)
    if scenario == "activity":
        hr += 30 + 10 * math.sin(index / 12)
        rr += 6
    metrics = {
        "heart_rate_bpm": round(hr, 1),
        "pulse_rate_bpm": round(hr, 1),
        "spo2_percent": round(98 + rng.uniform(-0.3, 0.3), 1),
        "respiratory_rate_per_min": round(rr, 1),
        "skin_temperature_c": None,
    }
    temperature_input = 33.4 + rng.uniform(-0.1, 0.1)
    quality = "synthetic"
    if scenario == "signal-loss" and count // 3 <= index < 2 * count // 3:
        metrics = {key: None for key in metrics}
        quality = "missing"
    else:
        sensor = temperature_sensor if temperature_sensor is not None else MAX30205Simulator()
        # Preserve the simulator's quantized return without rounding it again.
        metrics["skin_temperature_c"] = sensor.sample(temperature_input, measured_at)["temperature_c"]
    if scenario == "invalid" and index % 5 == 0:
        metrics["spo2_percent"] = 120
        quality = "deliberately_invalid"
    return {
        "schema_version": "demo.v1",
        "event_id": f"{session_id}:{index}",
        "device_id": "studywatch-sim-001",
        "simulated": True,
        "sequence": index,
        "measured_at": measured_at.isoformat(),
        "scenario": scenario,
        "quality": quality,
        "metrics": metrics,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--interval", type=float, default=1.0,
                        help="Espera entre registros en segundos; 0 acelera la generación")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario", choices=("baseline", "activity", "signal-loss", "invalid"),
                        default="baseline")
    parser.add_argument("--url", help="Endpoint HTTP existente; si se omite, solo imprime JSONL")
    args = parser.parse_args()
    if args.samples < 1 or not math.isfinite(args.interval) or args.interval < 0:
        parser.error("--samples debe ser >= 1 y --interval debe ser finito y >= 0")
    if args.url and (urlparse(args.url).scheme not in ("http", "https") or not urlparse(args.url).hostname):
        parser.error("--url debe ser una URL HTTP o HTTPS válida")

    rng = random.Random(args.seed)
    start = datetime.now(timezone.utc)
    session_id = uuid.uuid4().hex
    failures = 0
    accepted = 0
    temperature_sensor = MAX30205Simulator()
    for index in range(args.samples):
        event = make_event(index, args.samples, args.scenario, rng, start, session_id, temperature_sensor)
        payload = json.dumps(event, ensure_ascii=False, allow_nan=False)
        print(payload, flush=True)
        if args.url:
            headers = {"Content-Type": "application/json"}
            if os.environ.get("TELEMETRY_AUTHORIZATION"):
                headers["Authorization"] = os.environ["TELEMETRY_AUTHORIZATION"]
            request = Request(args.url, data=payload.encode("utf-8"), headers=headers, method="POST")
            try:
                with urlopen(request, timeout=5) as response:
                    if 200 <= response.status < 300:
                        accepted += 1
                    else:
                        failures += 1
                    print(f"Evento {index}: HTTP {response.status}", file=sys.stderr)
            except HTTPError as exc:
                failures += 1
                print(f"Evento {index}: HTTP {exc.code}; revisar validación y autenticación.", file=sys.stderr)
            except (URLError, OSError, ValueError):
                failures += 1
                print(f"Evento {index}: error de conexión o configuración HTTP.", file=sys.stderr)
        if index + 1 < args.samples and args.interval:
            time.sleep(args.interval)
    print(f"Generados: {args.samples}. HTTP aceptados: {accepted}. Fallos HTTP: {failures}.", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)

