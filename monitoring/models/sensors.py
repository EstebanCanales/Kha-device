"""Devices, revocable credentials, sensors, and enabled measurement channels."""

from django.core.exceptions import ValidationError
from django.db import models

from .shared import METRIC_UNITS, Metric, UUIDPrimaryKeyModel


class Device(UUIDPrimaryKeyModel):
    class Kind(models.TextChoices):
        HARNESS = "harness", "Harness"
        DOSIMETER = "dosimeter", "Dosimeter"
        GATEWAY = "gateway", "Gateway"

    class Source(models.TextChoices):
        SIMULATED = "simulated", "Simulated"
        HARDWARE = "hardware", "Hardware"

    identifier = models.CharField(max_length=80, unique=True)
    kind = models.CharField(max_length=12, choices=Kind)
    source = models.CharField(max_length=12, choices=Source)
    is_active = models.BooleanField(default=True)
    firmware_version = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return self.identifier

class DeviceCredential(UUIDPrimaryKeyModel):
    """Revocable verifier for one device; the bearer secret is never stored."""

    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="credentials")
    secret_hash = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Sensor(UUIDPrimaryKeyModel):
    identifier = models.CharField(max_length=80, unique=True)
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="sensors")
    channel = models.CharField(max_length=80)
    body_site = models.CharField(max_length=80, blank=True)
    reference_frame = models.CharField(max_length=80, blank=True)
    profile_version = models.CharField(max_length=80, blank=True)
    calibration_reference = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["device", "channel"], name="unique_device_channel")]

    def __str__(self):
        return self.identifier

class SensorCapability(UUIDPrimaryKeyModel):
    sensor = models.ForeignKey(Sensor, on_delete=models.PROTECT, related_name="capabilities")
    metric = models.CharField(max_length=50, choices=Metric)
    unit = models.CharField(max_length=20)
    enabled = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["sensor", "metric", "unit"], name="unique_sensor_metric_unit")]

    def clean(self):
        if self.unit not in METRIC_UNITS.get(self.metric, set()):
            raise ValidationError({"unit": "Unit is incompatible with metric."})
