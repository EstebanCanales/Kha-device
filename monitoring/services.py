"""Transactional ingestion, independent of the eventual sensor transport."""

import hashlib
import json
from datetime import timedelta, timezone as utc_timezone

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from .models import CounterEpoch, DeviceCredential, Measurement, MonitoringSession, Sensor, SessionDevice, TelemetryPacket


class PacketConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "packet_id was already used for different content."
    default_code = "packet_conflict"


def _model_error(error):
    return ValidationError(error.message_dict if hasattr(error, "message_dict") else error.messages)


def _canonical_hash(packet, schema_version):
    readings = []
    for reading in packet["readings"]:
        value = reading["value"]
        readings.append({
            "sensor_id": reading["sensor_id"],
            "metric": reading["metric"],
            "value": None if value is None else str(value.normalize()),
            "unit": reading["unit"],
            "quality": reading["quality"],
            "counter_epoch": str(reading.get("counter_epoch")) if reading.get("counter_epoch") else None,
            "method": reading.get("method", ""),
            "method_version": reading.get("method_version", ""),
        })
    canonical = {
        "schema_version": schema_version,
        "device_id": packet["device_id"],
        "session_id": packet["session_id"],
        "observed_at": packet["observed_at"].astimezone(utc_timezone.utc).isoformat(),
        "source": packet["source"],
        "readings": sorted(readings, key=lambda item: (item["sensor_id"], item["metric"])),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _existing_status(device, packet_id, digest):
    existing = TelemetryPacket.objects.filter(device=device, packet_id=packet_id).first()
    if existing is None:
        return None
    if existing.content_sha256 != digest:
        raise PacketConflict()
    return {"packet_id": str(packet_id), "status": "duplicate"}


def _insert_packet(packet, schema_version, credential):
    device = credential.device
    if packet["device_id"] != device.identifier:
        raise PermissionDenied("Credential cannot send for this device.")
    if packet["source"] != device.source:
        raise ValidationError({"source": "Source must match the registered device."})
    digest = _canonical_hash(packet, schema_version)
    duplicate = _existing_status(device, packet["packet_id"], digest)
    if duplicate:
        return duplicate

    session = MonitoringSession.objects.filter(identifier=packet["session_id"]).first()
    if session is None:
        raise PermissionDenied("Device is not assigned to this session at observed_at.")
    observed_at = packet["observed_at"]
    if observed_at > timezone.now() + timedelta(seconds=settings.TELEMETRY_FUTURE_SKEW_SECONDS):
        raise ValidationError({"observed_at": "Timestamp exceeds the allowed future clock tolerance."})
    assignment = SessionDevice.objects.filter(
        session=session, device=device, assigned_at__lte=observed_at
    ).filter(Q(released_at__isnull=True) | Q(released_at__gt=observed_at)).first()
    if assignment is None:
        raise PermissionDenied("Device is not assigned to this session at observed_at.")

    record = TelemetryPacket(
        packet_id=packet["packet_id"], schema_version=schema_version, assignment=assignment,
        device=device, observed_at=observed_at, source=packet["source"], content_sha256=digest,
    )
    try:
        record.full_clean(validate_unique=False, validate_constraints=False)
    except DjangoValidationError as error:
        raise _model_error(error) from error
    try:
        # The unique (device, packet_id) constraint resolves concurrent retries.
        with transaction.atomic():
            record.save()
    except IntegrityError:
        duplicate = _existing_status(device, packet["packet_id"], digest)
        if duplicate:
            return duplicate
        raise

    for reading in packet["readings"]:
        sensor = Sensor.objects.filter(identifier=reading["sensor_id"], device=device, is_active=True).first()
        if sensor is None:
            raise ValidationError({"sensor_id": "Active sensor not found on this device."})
        epoch = None
        if reading.get("counter_epoch"):
            epoch = CounterEpoch.objects.filter(
                identifier=reading["counter_epoch"], sensor=sensor, assignment=assignment
            ).first()
            if epoch is None:
                raise ValidationError({"counter_epoch": "Counter epoch does not match sensor and assignment."})
        measurement = Measurement(
            packet=record, sensor=sensor, metric=reading["metric"], value=reading["value"],
            unit=reading["unit"], quality=reading["quality"], profile_version=sensor.profile_version,
            method=reading.get("method", ""), method_version=reading.get("method_version", ""),
            counter_epoch=epoch,
        )
        try:
            measurement.full_clean()
        except DjangoValidationError as error:
            raise _model_error(error) from error
        measurement.save()
    return {"packet_id": str(packet["packet_id"]), "status": "inserted"}


@transaction.atomic
def ingest_batch(validated_data, credential: DeviceCredential):
    results = [
        _insert_packet(packet, validated_data["schema_version"], credential)
        for packet in validated_data["packets"]
    ]
    return {
        "packets": results,
        "inserted": sum(result["status"] == "inserted" for result in results),
        "duplicates": sum(result["status"] == "duplicate" for result in results),
    }
