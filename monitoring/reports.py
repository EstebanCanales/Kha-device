"""Bounded, descriptive reports; no inference, interpolation, or dose calculations."""

import json

from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from .dosimeter_profile import CHANNELS
from .models import Measurement, Metric, MonitoringSession
from .serializers import MeasurementSerializer

MAX_REPORT_READINGS = 1000
VITAL_METRICS = {
    Metric.HEART_RATE, Metric.PULSE_RATE, Metric.RESPIRATORY_RATE,
    Metric.SPO2,
}
BODY_TEMPERATURE_METRICS = {Metric.SKIN_TEMPERATURE}
DOSIMETER_METRICS = set(CHANNELS) | {
    Metric.EQUIVALENT_DOSE_RATE, Metric.EQUIVALENT_DOSE_CUMULATIVE,
    Metric.PERSONAL_DOSE_EQUIVALENT_RATE, Metric.PERSONAL_DOSE_EQUIVALENT_CUMULATIVE,
}
REPORT_NOTES = [
    "Descriptive acquisition report; no diagnosis, risk assessment, or AI inference.",
    "Readings are grouped by session and observation window, not synchronized or interpolated.",
    "Latest means latest observed reading in this window, including missing or unreliable quality; it does not imply current status.",
    "Missing readings remain null; absent domains indicate no stored readings in this window, not zero exposure or normal health.",
    "Original units and counter epochs remain separate. Never sum cumulative readings or infer dose from rates.",
    "Sampling schedules are unknown; report counts do not prove continuous monitoring or identify every transmission gap.",
    "Status codes: 0 unknown, 1 ok, 2 fault. dose_rate_increase: 0 false, 1 true; this is not a hazard threshold.",
    "Body temperature currently contains skin_temperature only; it is not core temperature. Internal dosimeter temperature remains dosimeter data.",
]


def build_report(*, user, session_id, source, observed_from, observed_to):
    """Authorize here as well as at the HTTP layer for future internal consumers."""
    sessions = MonitoringSession.objects.all()
    if not user or not user.is_authenticated or not user.is_active:
        raise NotFound()
    if not user.is_staff:
        sessions = sessions.filter(authorized_users=user)
    session = sessions.filter(pk=session_id).first()
    if session is None:
        raise NotFound()
    # Validate internal callers with the same contract used by the endpoint.
    from .report_serializers import ReportQuerySerializer
    query = ReportQuerySerializer(data={
        "source": source, "observed_from": observed_from.isoformat(), "observed_to": observed_to.isoformat(),
    })
    query.is_valid(raise_exception=True)
    generated_at = timezone.now()
    readings = list(Measurement.objects.select_related("packet__device", "sensor", "counter_epoch").filter(
        packet__assignment__session=session, packet__source=source,
        packet__observed_at__gte=observed_from, packet__observed_at__lt=observed_to,
        packet__received_at__lte=generated_at, metric__in=VITAL_METRICS | BODY_TEMPERATURE_METRICS | DOSIMETER_METRICS,
    ).order_by("packet__observed_at", "id")[:MAX_REPORT_READINGS + 1])
    if len(readings) > MAX_REPORT_READINGS:
        raise ValidationError(f"Report exceeds {MAX_REPORT_READINGS} readings. Request a smaller observation window; no partial report was generated.")
    grouped = {"vital_signs": {}, "body_temperature": {}, "dosimeter": {}}
    for reading in readings:
        row = dict(MeasurementSerializer(reading).data)
        if reading.metric in VITAL_METRICS:
            domain = "vital_signs"
        elif reading.metric in BODY_TEMPERATURE_METRICS:
            domain = "body_temperature"
        else:
            domain = "dosimeter"
        row["category"] = domain
        key = (reading.sensor_id, reading.metric, reading.unit, reading.counter_epoch_id,
               reading.profile_version, reading.method, reading.method_version)
        series = grouped[domain].setdefault(key, {
            "category": domain, "device_id": reading.packet.device.identifier,
            **{name: row[name] for name in ("sensor_id", "metric", "unit", "counter_epoch", "profile_version", "method", "method_version")},
            "quality_counts": {"valid": 0, "unreliable": 0, "missing": 0}, "readings": [],
        })
        series["readings"].append(row)
        series["quality_counts"][reading.quality] += 1
        series["latest"] = row
    domains = {}
    for domain, series in grouped.items():
        domains[domain] = {
            "status": "available" if series else "no_data",
            "measurement_count": sum(len(item["readings"]) for item in series.values()),
            "series": list(series.values()),
        }
    return {
        "schema_version": "combined-telemetry-report.v2", "generated_at": generated_at.isoformat(), "source": source,
        "session": {
            "id": str(session.pk), "participant_id": str(session.participant_id),
            "started_at": session.started_at.isoformat(), "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "gravity_context": session.gravity_context,
        },
        "window": {"observed_from": observed_from.isoformat(), "observed_to": observed_to.isoformat(), "bounds": "[observed_from, observed_to)"},
        "measurement_count": len(readings),
        "missing_domains": [name for name, domain in domains.items() if domain["status"] == "no_data"],
        "notes": REPORT_NOTES.copy(), "domains": domains,
    }


def report_as_text(report):
    """Readable text with JSON-escaped data and all evidence retained for a model."""
    lines = ["Combined vital signs and dosimeter report", f"Schema: {report['schema_version']}",
             f"Generated at: {report['generated_at']}", f"Source: {report['source']}",
             "Session: " + json.dumps(report["session"], sort_keys=True),
             "Observation window: " + json.dumps(report["window"], sort_keys=True),
             f"Total readings: {report['measurement_count']}",
             "Missing domains: " + json.dumps(report["missing_domains"])]
    lines.extend("Note: " + note for note in report["notes"])
    for name, domain in report["domains"].items():
        lines.extend(["", f"{name}: {domain['status']} ({domain['measurement_count']} readings)"])
        for series in domain["series"]:
            lines.append("Series: " + json.dumps({key: value for key, value in series.items() if key not in {"readings", "latest"}}, sort_keys=True))
            lines.append("Latest observed: " + json.dumps(series["latest"], sort_keys=True))
            lines.extend("Reading: " + json.dumps(row, sort_keys=True) for row in series["readings"])
    return "\n".join(lines) + "\n"
