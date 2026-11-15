"""Immutable ingested packets, scalar measurements, and optional ECG samples."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .assignments import CounterEpoch, SessionDevice
from .sensors import Device, Sensor, SensorCapability
from .shared import CUMULATIVE_METRICS, METRIC_UNITS, Metric, UUIDPrimaryKeyModel


class TelemetryPacket(UUIDPrimaryKeyModel):
    packet_id = models.UUIDField()
    schema_version = models.PositiveSmallIntegerField()
    assignment = models.ForeignKey(SessionDevice, on_delete=models.PROTECT, related_name="packets")
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="packets")
    observed_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=12, choices=Device.Source)
    content_sha256 = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["device", "packet_id"], name="unique_device_packet")]
        indexes = [models.Index(fields=["assignment", "observed_at", "id"])]

    def clean(self):
        if self.assignment_id and self.device_id and self.assignment.device_id != self.device_id:
            raise ValidationError("Packet device must match the assignment.")
        if self.device_id and self.source != self.device.source:
            raise ValidationError("Packet source must match the registered device.")
        if self.assignment_id and self.observed_at:
            if self.observed_at < self.assignment.assigned_at or (self.assignment.released_at and self.observed_at >= self.assignment.released_at):
                raise ValidationError("Packet time is outside the device assignment.")
            session = self.assignment.session
            if self.observed_at < session.started_at or (session.ended_at and self.observed_at >= session.ended_at):
                raise ValidationError("Packet time is outside the monitoring session.")

class Measurement(UUIDPrimaryKeyModel):
    class Quality(models.TextChoices):
        VALID = "valid", "Valid"
        UNRELIABLE = "unreliable", "Unreliable"
        MISSING = "missing", "Missing"

    packet = models.ForeignKey(TelemetryPacket, on_delete=models.PROTECT, related_name="measurements")
    sensor = models.ForeignKey(Sensor, on_delete=models.PROTECT, related_name="measurements")
    metric = models.CharField(max_length=50, choices=Metric)
    value = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    unit = models.CharField(max_length=20)
    quality = models.CharField(max_length=12, choices=Quality)
    profile_version = models.CharField(max_length=80, blank=True)
    method = models.CharField(max_length=80, blank=True)
    method_version = models.CharField(max_length=80, blank=True)
    counter_epoch = models.ForeignKey(CounterEpoch, null=True, blank=True, on_delete=models.PROTECT, related_name="measurements")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(quality="missing", value__isnull=True) | Q(quality__in=["valid", "unreliable"], value__isnull=False)), name="measurement_quality_value"),
            models.UniqueConstraint(fields=["packet", "sensor", "metric"], name="unique_packet_sensor_metric"),
        ]
        indexes = [models.Index(fields=["sensor", "metric", "packet"]), models.Index(fields=["metric", "packet"])]

    def clean(self):
        errors = {}
        if self.unit not in METRIC_UNITS.get(self.metric, set()):
            errors["unit"] = "Unit is incompatible with metric."
        if self.sensor_id and self.packet_id and self.sensor.device_id != self.packet.device_id:
            errors["sensor"] = "Sensor must belong to the packet device."
        if self.sensor_id and not SensorCapability.objects.filter(sensor_id=self.sensor_id, metric=self.metric, unit=self.unit, enabled=True).exists():
            errors["metric"] = "Metric and unit are not enabled for this sensor."
        if self.value is not None:
            if self.metric in {Metric.DIS_CHAMBER_STATUS, Metric.STORAGE_STATUS} and self.value not in {0, 1, 2}:
                errors["value"] = "Status must be 0 (unknown), 1 (ok), or 2 (fault)."
            if self.metric == Metric.DOSE_RATE_INCREASE and self.value not in {0, 1}:
                errors["value"] = "Increase flag must be 0 or 1."
            if self.metric in {Metric.EXPOSURE_DURATION, Metric.MEASUREMENT_INTERVAL, Metric.MISSION_ELAPSED_TIME} and self.value < 0:
                errors["value"] = "Elapsed time cannot be negative."
        if self.metric in CUMULATIVE_METRICS and not self.counter_epoch_id:
            errors["counter_epoch"] = "Cumulative dose requires a counter epoch."
        if self.counter_epoch_id and self.sensor_id and self.packet_id:
            if self.counter_epoch.sensor_id != self.sensor_id or self.counter_epoch.assignment_id != self.packet.assignment_id:
                errors["counter_epoch"] = "Counter epoch must match sensor and assignment."
            elif self.packet.observed_at < self.counter_epoch.started_at or (
                self.counter_epoch.ended_at and self.packet.observed_at >= self.counter_epoch.ended_at
            ):
                errors["counter_epoch"] = "Measurement time is outside the counter epoch."
        if errors:
            raise ValidationError(errors)

class ECGSample(UUIDPrimaryKeyModel):
    """Optional raw sample; no ECG acquisition or interpretation is implied."""

    packet = models.ForeignKey(TelemetryPacket, on_delete=models.PROTECT, related_name="ecg_samples")
    sensor = models.ForeignKey(Sensor, on_delete=models.PROTECT, related_name="ecg_samples")
    channel = models.CharField(max_length=40)
    sample_index = models.PositiveIntegerField()
    observed_at = models.DateTimeField()
    amplitude = models.DecimalField(max_digits=20, decimal_places=9)
    unit = models.CharField(max_length=4, choices=[("uV", "Microvolt"), ("mV", "Millivolt")])
    profile_version = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["packet", "sensor", "channel", "sample_index"], name="unique_ecg_sample")]
        indexes = [models.Index(fields=["sensor", "observed_at", "id"])]

    def clean(self):
        if self.sensor_id and self.packet_id and self.sensor.device_id != self.packet.device_id:
            raise ValidationError("ECG sensor must belong to the packet device.")
        if self.sensor_id and not SensorCapability.objects.filter(sensor_id=self.sensor_id, metric=Metric.ECG, unit=self.unit, enabled=True).exists():
            raise ValidationError("ECG capability is not enabled for this sensor and unit.")
