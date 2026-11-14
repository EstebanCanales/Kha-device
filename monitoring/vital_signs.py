"""Adapter for the synthetic study-watch demo.v1 format, not a hardware protocol."""

import math
import uuid

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.response import Response

from .models import DeviceCredential, SessionDevice
from .serializers import (
    AwareDateTimeField,
    BatchInputSerializer,
    BatchOutputSerializer,
    StrictSerializer,
)
from .services import ingest_batch
from .views import TelemetryBatchView

METRICS = {
    "heart_rate_bpm": ("heart_rate", "bpm"),
    "pulse_rate_bpm": ("pulse_rate", "bpm"),
    "spo2_percent": ("spo2", "%"),
    "respiratory_rate_per_min": ("respiratory_rate", "breaths/min"),
    "skin_temperature_c": ("skin_temperature", "degC"),
}


class VitalSignsSerializer(StrictSerializer):
    schema_version = serializers.ChoiceField(choices=["demo.v1"])
    event_id = serializers.CharField(max_length=120)
    device_id = serializers.CharField(max_length=80)
    simulated = serializers.BooleanField()
    sequence = serializers.IntegerField(min_value=0)
    measured_at = AwareDateTimeField()
    scenario = serializers.ChoiceField(choices=["baseline", "activity", "signal-loss", "invalid"])
    quality = serializers.ChoiceField(choices=["synthetic", "missing", "deliberately_invalid"])
    metrics = serializers.DictField()

    def validate(self, data):
        if data["simulated"] is not True:
            raise serializers.ValidationError("This endpoint accepts simulated events only.")
        if data["quality"] == "deliberately_invalid":
            raise serializers.ValidationError("Deliberately invalid simulator events are rejected.")
        if set(data["metrics"]) != set(METRICS):
            raise serializers.ValidationError({"metrics": "Exactly the five demo.v1 metrics are required."})
        for key, value in data["metrics"].items():
            if data["quality"] == "missing":
                if value is not None:
                    raise serializers.ValidationError({key: "Missing readings must be null."})
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise serializers.ValidationError({key: "A finite JSON number is required."})
            if key == "spo2_percent" and value is not None and not 0 <= value <= 100:
                raise serializers.ValidationError({key: "A percentage must be between 0 and 100."})
        return data


def adapt_event(event, credential):
    if event["device_id"] != credential.device.identifier or credential.device.source != "simulated":
        raise PermissionDenied("Credential must match the simulated device.")
    instant = event["measured_at"]
    assignments = SessionDevice.objects.select_related("session").filter(
        device=credential.device, assigned_at__lte=instant,
    ).filter(Q(released_at__isnull=True) | Q(released_at__gt=instant))
    if assignments.count() != 1:
        raise PermissionDenied("Exactly one historical device assignment is required.")
    assignment = assignments.get()
    readings = []
    for key, (metric, unit) in METRICS.items():
        value = event["metrics"][key]
        readings.append({
            "sensor_id": f"{event['device_id']}-{metric}", "metric": metric,
            "unit": unit, "value": None if value is None else str(value),
            "quality": "missing" if value is None else "valid",
            "method": f"vital_signs:{event['scenario']}:{event['sequence']}", "method_version": "demo.v1",
        })
    payload = {"schema_version": 1, "packets": [{
        "packet_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"kha:demo.v1:{event['device_id']}:{event['event_id']}")),
        "device_id": event["device_id"], "session_id": assignment.session.identifier,
        "observed_at": instant.isoformat(), "source": "simulated", "readings": readings,
    }]}
    serializer = BatchInputSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class VitalSignsView(TelemetryBatchView):
    @extend_schema(request=VitalSignsSerializer, responses={200: BatchOutputSerializer, 201: BatchOutputSerializer})
    def post(self, request):
        if not isinstance(request.auth, DeviceCredential):
            raise NotAuthenticated("Device credentials are required.")
        serializer = VitalSignsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ingest_batch(adapt_event(serializer.validated_data, request.auth), request.auth)
        return Response(result, status=201 if result["inserted"] else 200)
