"""Configuration and version-one telemetry contract serializers."""

import re
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import (
    CounterEpoch,
    Device,
    Measurement,
    Metric,
    MonitoringSession,
    Participant,
    Sensor,
    SensorCapability,
    SessionDevice,
)


class CleanModelSerializer(serializers.ModelSerializer):
    """Run model relationship checks for API configuration writes."""

    @transaction.atomic
    def create(self, validated_data):
        users = validated_data.pop("authorized_users", None)
        instance = self.Meta.model(**validated_data)
        try:
            instance.full_clean()
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict if hasattr(error, "message_dict") else error.messages) from error
        instance.save()
        if users is not None:
            instance.authorized_users.set(users)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        users = validated_data.pop("authorized_users", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.full_clean()
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict if hasattr(error, "message_dict") else error.messages) from error
        instance.save()
        if users is not None:
            instance.authorized_users.set(users)
        return instance


def reject_changed(instance, data, fields):
    errors = {}
    for field in fields:
        if field in data and getattr(instance, field) != data[field]:
            errors[field] = "This field cannot be changed after creation."
    if errors:
        raise serializers.ValidationError(errors)


class ParticipantSerializer(CleanModelSerializer):
    class Meta:
        model = Participant
        fields = ("id", "pseudonym", "created_at")
        read_only_fields = ("id", "created_at")

    def validate(self, data):
        if self.instance and self.instance.sessions.exists():
            reject_changed(self.instance, data, ("pseudonym",))
        return data


class SessionSerializer(CleanModelSerializer):
    authorized_users = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(is_active=True), many=True, required=False, write_only=True
    )

    class Meta:
        model = MonitoringSession
        fields = ("id", "identifier", "participant", "started_at", "ended_at", "gravity_context", "gravity_context_source", "authorized_users")
        read_only_fields = ("id",)

    def validate(self, data):
        if self.instance:
            reject_changed(self.instance, data, ("identifier", "participant", "started_at"))
            if self.instance.device_assignments.filter(packets__isnull=False).exists():
                reject_changed(self.instance, data, ("gravity_context", "gravity_context_source"))
                ended = data.get("ended_at")
                if ended and self.instance.device_assignments.filter(packets__observed_at__gte=ended).exists():
                    raise serializers.ValidationError({"ended_at": "Existing packets extend beyond this time."})
        return data


class DeviceSerializer(CleanModelSerializer):
    class Meta:
        model = Device
        fields = ("id", "identifier", "kind", "source", "is_active", "firmware_version")
        read_only_fields = ("id",)

    def validate(self, data):
        if self.instance:
            reject_changed(self.instance, data, ("identifier", "kind", "source"))
        return data


class SensorSerializer(CleanModelSerializer):
    class Meta:
        model = Sensor
        fields = ("id", "identifier", "device", "channel", "body_site", "reference_frame", "profile_version", "calibration_reference", "is_active")
        read_only_fields = ("id",)

    def validate(self, data):
        if self.instance:
            reject_changed(self.instance, data, ("identifier", "device", "channel"))
            if self.instance.measurements.exists() or self.instance.ecg_samples.exists():
                reject_changed(self.instance, data, ("body_site", "reference_frame", "profile_version", "calibration_reference"))
        return data


class SensorCapabilitySerializer(CleanModelSerializer):
    class Meta:
        model = SensorCapability
        fields = ("id", "sensor", "metric", "unit", "enabled")
        read_only_fields = ("id",)

    def validate(self, data):
        if self.instance:
            reject_changed(self.instance, data, ("sensor", "metric", "unit"))
        return data


class SessionDeviceSerializer(CleanModelSerializer):
    class Meta:
        model = SessionDevice
        fields = ("id", "session", "device", "assigned_at", "released_at")
        read_only_fields = ("id",)

    def validate(self, data):
        if self.instance:
            reject_changed(self.instance, data, ("session", "device", "assigned_at"))
            released = data.get("released_at")
            if released and self.instance.packets.filter(observed_at__gte=released).exists():
                raise serializers.ValidationError({"released_at": "Existing packets extend beyond this time."})
        return data


class CounterEpochSerializer(CleanModelSerializer):
    class Meta:
        model = CounterEpoch
        fields = ("id", "identifier", "assignment", "sensor", "started_at", "ended_at", "reference")
        read_only_fields = ("id", "identifier")

    def validate(self, data):
        if self.instance:
            reject_changed(self.instance, data, ("assignment", "sensor", "started_at"))
            ended = data.get("ended_at")
            if ended and self.instance.measurements.filter(packet__observed_at__gte=ended).exists():
                raise serializers.ValidationError({"ended_at": "Existing measurements extend beyond this time."})
        return data


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected a JSON object.")
        extra = set(data) - set(self.fields)
        if extra:
            raise serializers.ValidationError({name: "Unknown field." for name in sorted(extra)})
        return super().to_internal_value(data)


class AwareDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, value):
        if not isinstance(value, str) or not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value):
            raise serializers.ValidationError("An ISO 8601 timestamp with timezone is required.")
        return super().to_internal_value(value)


@extend_schema_field({"type": "string", "pattern": r"^[+-]?\d+(?:\.\d+)?$", "maxLength": 64})
class DecimalStringField(serializers.Field):
    def to_internal_value(self, value):
        if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(r"[+-]?(?:\d+)(?:\.\d+)?", value):
            raise serializers.ValidationError("Use a finite decimal string.")
        try:
            number = Decimal(value)
        except InvalidOperation as error:
            raise serializers.ValidationError("Invalid decimal value.") from error
        whole, _, fraction = value.lstrip("+-").partition(".")
        if len(whole.lstrip("0") or "0") > 18 or len(fraction) > 12:
            raise serializers.ValidationError("Maximum precision is 18 integer and 12 fractional digits.")
        return number

    def to_representation(self, value):
        return str(value)


class ReadingInputSerializer(StrictSerializer):
    sensor_id = serializers.CharField(max_length=80)
    metric = serializers.ChoiceField(choices=Metric.choices)
    value = DecimalStringField(allow_null=True)
    unit = serializers.CharField(max_length=20)
    quality = serializers.ChoiceField(choices=Measurement.Quality.choices)
    counter_epoch = serializers.UUIDField(required=False, allow_null=True)
    method = serializers.CharField(max_length=80, required=False, allow_blank=True)
    method_version = serializers.CharField(max_length=80, required=False, allow_blank=True)

    def validate(self, data):
        if (data["quality"] == Measurement.Quality.MISSING) != (data["value"] is None):
            raise serializers.ValidationError("Missing quality requires null; other qualities require a value.")
        if data.get("method") and not data.get("method_version"):
            raise serializers.ValidationError("method_version is required when method is set.")
        return data


class PacketInputSerializer(StrictSerializer):
    packet_id = serializers.UUIDField()
    device_id = serializers.CharField(max_length=80)
    session_id = serializers.CharField(max_length=80)
    observed_at = AwareDateTimeField()
    source = serializers.ChoiceField(choices=Device.Source.choices)
    readings = ReadingInputSerializer(many=True, allow_empty=False, max_length=32)

    def validate_readings(self, readings):
        keys = [(reading["sensor_id"], reading["metric"]) for reading in readings]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError("A sensor and metric may appear only once per packet.")
        return readings


class BatchInputSerializer(StrictSerializer):
    schema_version = serializers.ChoiceField(choices=[1])
    packets = PacketInputSerializer(many=True, allow_empty=False, max_length=100)


class PacketStatusSerializer(serializers.Serializer):
    packet_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["inserted", "duplicate"])


class BatchOutputSerializer(serializers.Serializer):
    packets = PacketStatusSerializer(many=True)
    inserted = serializers.IntegerField()
    duplicates = serializers.IntegerField()


class MeasurementSerializer(serializers.ModelSerializer):
    packet_id = serializers.UUIDField(source="packet.packet_id", read_only=True)
    sensor_id = serializers.CharField(source="sensor.identifier", read_only=True)
    source = serializers.CharField(source="packet.source", read_only=True)
    observed_at = serializers.DateTimeField(source="packet.observed_at", read_only=True)
    received_at = serializers.DateTimeField(source="packet.received_at", read_only=True)
    counter_epoch = serializers.UUIDField(source="counter_epoch.identifier", read_only=True, allow_null=True)

    class Meta:
        model = Measurement
        fields = ("id", "packet_id", "sensor_id", "metric", "value", "unit", "quality", "source", "observed_at", "received_at", "profile_version", "method", "method_version", "counter_epoch")
