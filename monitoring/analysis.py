"""Session analysis: personal baseline, change from baseline, dose counters, and data gaps.

This is descriptive statistics over stored readings, not a diagnosis. The tuning
constants below are provisional engineering choices: they are not medical or
radiological thresholds, and none has been validated for clinical or space use.
A "shift" only says that recent readings moved away from this person's own early
readings in the same session.
"""

from datetime import datetime, timedelta
from statistics import median

from django.utils import timezone

from .models import Measurement, Metric

# Metrics tracked against a personal baseline: (metric, minimum spread in the metric's unit).
# The floor keeps a very steady baseline from turning tiny wobbles into "shifts".
TRACKED = (
    (Metric.HEART_RATE, 2.0),
    (Metric.SPO2, 0.5),
    (Metric.RESPIRATORY_RATE, 1.0),
    (Metric.SKIN_TEMPERATURE, 0.15),
)
MIN_POINTS = 20
BASELINE_FRACTION = 0.4
BASELINE_MIN = 10
RECENT_POINTS = 10
Z_SHIFT = 3.0
# Dose rate: recent counter increase per hour compared with the early rate.
RATE_RATIO = 3.0
RATE_MIN_POINTS = 10
GAP_FACTOR = 5  # a gap is a pause longer than this many typical sampling steps
MAX_GAPS = 5


def _iso(value: datetime | None):
    return value.isoformat() if value else None


def _robust_spread(values: list[float], centre: float, floor: float) -> float:
    """Median absolute deviation scaled to a standard deviation, never below the floor."""
    mad = median(abs(v - centre) for v in values)
    return max(1.4826 * mad, floor)


def _baseline_change(series, unit, floor):
    """series is a time-ordered list of (observed_at, value)."""
    n = len(series)
    if n < MIN_POINTS:
        return {"status": "insufficient_data", "readings": n, "needed": MIN_POINTS}
    base_n = max(BASELINE_MIN, int(n * BASELINE_FRACTION))
    recent_n = min(RECENT_POINTS, n - base_n)
    base, recent = series[:base_n], series[-recent_n:]
    base_values = [v for _, v in base]
    centre = median(base_values)
    spread = _robust_spread(base_values, centre, floor)
    recent_centre = median(v for _, v in recent)
    z = (recent_centre - centre) / spread
    status = "stable" if abs(z) < Z_SHIFT else ("shift_up" if z > 0 else "shift_down")
    return {
        "status": status, "unit": unit, "z_score": round(z, 2), "readings": n,
        "baseline": {"median": round(centre, 3), "spread": round(spread, 3), "readings": base_n,
                     "from": _iso(base[0][0]), "to": _iso(base[-1][0])},
        "recent": {"median": round(recent_centre, 3), "readings": recent_n,
                   "from": _iso(recent[0][0]), "to": _iso(recent[-1][0])},
    }


def _rate(points):
    """Counter increase per hour between the first and last point of a time-ordered list."""
    (t0, v0), (t1, v1) = points[0], points[-1]
    hours = (t1 - t0).total_seconds() / 3600
    return None if hours <= 0 else (v1 - v0) / hours


def _dose_chambers(rows):
    """Cumulative dose per sensor and counter epoch. Counters are never added across epochs or sensors."""
    groups: dict[tuple, list] = {}
    meta: dict[tuple, dict] = {}
    for at, value, unit, sensor, channel, calibration, epoch in rows:
        key = (sensor, epoch)
        groups.setdefault(key, []).append((at, value))
        meta[key] = {"sensor": sensor, "channel": channel, "unit": unit, "counter_epoch": str(epoch),
                     "calibration_reference": calibration}
    chambers = []
    for key, points in groups.items():
        points.sort()
        latest_at, latest = points[-1]
        entry = {**meta[key], "latest_value": round(latest, 6), "latest_observed_at": _iso(latest_at),
                 "readings": len(points)}
        # A cumulative counter that goes down inside one epoch is a data-integrity problem, not a result.
        entry["counter_decreased"] = any(b < a for (_, a), (_, b) in zip(points, points[1:]))
        if len(points) >= RATE_MIN_POINTS:
            split = max(2, int(len(points) * BASELINE_FRACTION))
            early, recent = points[:split], points[-max(2, int(len(points) * 0.15)):]
            early_rate, recent_rate = _rate(early), _rate(recent)
            entry["rate_per_hour"] = {"early": early_rate and round(early_rate, 6),
                                      "recent": recent_rate and round(recent_rate, 6)}
            if early_rate and early_rate > 0 and recent_rate is not None:
                ratio = recent_rate / early_rate
                entry["rate_ratio"] = round(ratio, 2)
                entry["status"] = "rate_up" if ratio >= RATE_RATIO else "stable"
            else:
                entry["status"] = "insufficient_data"
        else:
            entry["status"] = "insufficient_data"
        chambers.append(entry)
    return sorted(chambers, key=lambda c: (c["channel"], c["latest_observed_at"] or ""))


def _gaps(times: list[datetime]):
    """Pauses in the packet timeline, relative to the typical sampling step."""
    if len(times) < 3:
        return []
    deltas = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    step = median(deltas)
    if step <= 0:
        return []
    found = [
        {"from": _iso(a), "to": _iso(b), "seconds": int(d)}
        for a, b, d in zip(times, times[1:], deltas) if d > step * GAP_FACTOR
    ]
    return sorted(found, key=lambda g: -g["seconds"])[:MAX_GAPS]


def analyze_session(session, source: str) -> dict:
    """Describe a session's stored readings for one provenance (`simulated` or `hardware`)."""
    rows = Measurement.objects.filter(packet__assignment__session=session, packet__source=source)
    # Quality summary and packet timeline use every stored reading, including missing ones.
    stats = {}
    for metric, quality in rows.values_list("metric", "quality").iterator():
        entry = stats.setdefault(metric, {"valid": 0, "unreliable": 0, "missing": 0})
        entry[quality] += 1
    times = sorted(set(rows.values_list("packet__observed_at", flat=True)))

    metrics = {}
    missing_data = []
    for metric, floor in TRACKED:
        valid = rows.filter(metric=metric, quality="valid").order_by("packet__observed_at", "id")
        data = list(valid.values_list("packet__observed_at", "value", "unit"))
        counts = stats.get(metric, {"valid": 0, "unreliable": 0, "missing": 0})
        if not data:
            missing_data.append({"code": "no_valid_readings", "metric": str(metric)})
            metrics[metric] = {"status": "no_data", "quality_counts": counts}
            continue
        units = {unit for _, _, unit in data}
        if len(units) != 1:
            metrics[metric] = {"status": "mixed_units", "units": sorted(units), "quality_counts": counts}
            continue
        series = [(at, float(value)) for at, value, _ in data]
        metrics[metric] = {**_baseline_change(series, units.pop(), floor), "quality_counts": counts}
        if counts["missing"]:
            missing_data.append({"code": "missing_readings", "metric": str(metric), "count": counts["missing"]})
        if counts["unreliable"]:
            missing_data.append({"code": "unreliable_readings", "metric": str(metric), "count": counts["unreliable"]})

    dose_rows = rows.filter(metric=Metric.ABSORBED_DOSE_CUMULATIVE, quality="valid").values_list(
        "packet__observed_at", "value", "unit", "sensor__identifier", "sensor__channel",
        "sensor__calibration_reference", "counter_epoch__identifier",
    )
    chambers = _dose_chambers([(a, float(v), u, s, c, k, e) for a, v, u, s, c, k, e in dose_rows])
    if not chambers:
        missing_data.append({"code": "no_dose_readings", "metric": str(Metric.ABSORBED_DOSE_CUMULATIVE)})

    gaps = _gaps(times)
    if gaps:
        missing_data.append({"code": "timeline_gaps", "count": len(gaps)})

    changes = [
        {"metric": metric, "status": result["status"], "z_score": result["z_score"], "unit": result["unit"]}
        for metric, result in metrics.items() if result["status"] in ("shift_up", "shift_down")
    ] + [
        {"metric": f"dose:{c['channel']}", "status": c["status"], "rate_ratio": c.get("rate_ratio"), "unit": c["unit"]}
        for c in chambers if c["status"] == "rate_up"
    ]
    return {
        "session": session.identifier,
        "source": source,
        "participant": session.participant.pseudonym,
        "gravity_context": session.gravity_context,
        "window": {"first_observed_at": _iso(times[0]) if times else None,
                   "last_observed_at": _iso(times[-1]) if times else None, "packets": len(times),
                   "hours": round((times[-1] - times[0]).total_seconds() / 3600, 2) if times else 0},
        "method": "personal-baseline-median-mad", "method_version": "1",
        "notice": "Statistical change from this person's own early readings. Not a diagnosis or a medical alert.",
        "metrics": metrics,
        "dose": {"chambers": chambers},
        "changes": changes,
        "gaps": gaps,
        "missing_data": missing_data,
        "generated_at": timezone.now().isoformat(),
    }



# History shown in the dashboard charts. A day: simulated devices report every 30 minutes, so a shorter window
# would leave only a handful of points per chart.
SERIES_WINDOW = timedelta(hours=24)
SERIES_POINTS = 120
SERIES_MAX_ROWS = 20000


def sensor_series(session, source: str) -> list[dict]:
    """Latest valid reading and a short, downsampled history for every sensor and metric.

    One entry per sensor, metric, unit, and counter epoch, so cumulative counters are never merged.
    The window ends at the last stored packet, not at the current time.
    """
    rows = Measurement.objects.filter(
        packet__assignment__session=session, packet__source=source, quality="valid"
    )
    last = rows.order_by("-packet__observed_at").values_list("packet__observed_at", flat=True).first()
    if last is None:
        return []
    rows = (
        rows.filter(packet__observed_at__gte=last - SERIES_WINDOW)
        .order_by("packet__observed_at", "id")
        .values_list(
            "sensor__identifier", "sensor__device__kind", "metric", "unit", "value",
            "packet__observed_at", "counter_epoch__identifier",
        )[:SERIES_MAX_ROWS]
    )
    groups: dict[tuple, dict] = {}
    for sensor, kind, metric, unit, value, at, epoch in rows:
        key = (sensor, metric, unit, epoch)
        entry = groups.setdefault(key, {
            "sensor": sensor, "device_kind": kind, "metric": str(metric), "unit": unit,
            "counter_epoch": str(epoch) if epoch else None, "points": [],
        })
        entry["points"].append((at, float(value)))
    out = []
    for entry in groups.values():
        points = entry.pop("points")
        values = [v for _, v in points]
        step = max(1, -(-len(points) // SERIES_POINTS))
        sampled = points[::step]
        if sampled[-1] is not points[-1]:
            sampled.append(points[-1])
        entry.update(
            latest={"value": points[-1][1], "observed_at": _iso(points[-1][0])},
            min=min(values), max=max(values), readings=len(points),
            points=[[_iso(a), v] for a, v in sampled],
        )
        out.append(entry)
    return sorted(out, key=lambda e: (e["device_kind"], e["metric"], e["sensor"]))
