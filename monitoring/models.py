"""Acquisition records and explicitly versioned derived observations.

These models describe possible data. A metric is available only after a
SensorCapability has been configured for an actual or simulated sensor.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Metric(models.TextChoices):
    HEART_RATE = "heart_rate", "Heart rate"
    ECG = "ecg", "ECG signal"
    RESPIRATORY_RATE = "respiratory_rate", "Respiratory rate"
    SPO2 = "spo2", "Peripheral oxygen saturation estimate"
    SKIN_TEMPERATURE = "skin_temperature", "Skin temperature"
    ACCELERATION_X = "acceleration_x", "Acceleration X"
    ACCELERATION_Y = "acceleration_y", "Acceleration Y"
    ACCELERATION_Z = "acceleration_z", "Acceleration Z"
    ABSORBED_DOSE_RATE = "absorbed_dose_rate", "Absorbed dose rate"
    EQUIVALENT_DOSE_RATE = "equivalent_dose_rate", "Equivalent dose rate"
    PERSONAL_DOSE_EQUIVALENT_RATE = "personal_dose_equivalent_rate", "Personal dose equivalent rate"
    ABSORBED_DOSE_CUMULATIVE = "absorbed_dose_cumulative", "Cumulative absorbed dose"
    EQUIVALENT_DOSE_CUMULATIVE = "equivalent_dose_cumulative", "Cumulative equivalent dose"
    PERSONAL_DOSE_EQUIVALENT_CUMULATIVE = "personal_dose_equivalent_cumulative", "Cumulative personal dose equivalent"
    EXPOSURE_DURATION = "exposure_duration", "Recorded exposure duration"


METRIC_UNITS = {
    Metric.HEART_RATE: {"bpm"},
    Metric.ECG: {"uV", "mV"},
    Metric.RESPIRATORY_RATE: {"breaths/min"},
    Metric.SPO2: {"%"},
    Metric.SKIN_TEMPERATURE: {"degC"},
    Metric.ACCELERATION_X: {"m/s2"},
    Metric.ACCELERATION_Y: {"m/s2"},
    Metric.ACCELERATION_Z: {"m/s2"},
    Metric.ABSORBED_DOSE_RATE: {"Gy/h", "mGy/h", "uGy/h"},
    Metric.EQUIVALENT_DOSE_RATE: {"Sv/h", "mSv/h", "uSv/h"},
    Metric.PERSONAL_DOSE_EQUIVALENT_RATE: {"Sv/h", "mSv/h", "uSv/h"},
    Metric.ABSORBED_DOSE_CUMULATIVE: {"Gy", "mGy", "uGy"},
    Metric.EQUIVALENT_DOSE_CUMULATIVE: {"Sv", "mSv", "uSv"},
    Metric.PERSONAL_DOSE_EQUIVALENT_CUMULATIVE: {"Sv", "mSv", "uSv"},
    Metric.EXPOSURE_DURATION: {"s"},
}
CUMULATIVE_METRICS = {
    Metric.ABSORBED_DOSE_CUMULATIVE,
    Metric.EQUIVALENT_DOSE_CUMULATIVE,
    Metric.PERSONAL_DOSE_EQUIVALENT_CUMULATIVE,
}


class UUIDPrimaryKeyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class Participant(UUIDPrimaryKeyModel):
    pseudonym = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.pseudonym


class MonitoringSession(UUIDPrimaryKeyModel):
    class Gravity(models.TextChoices):
        EARTH = "earth", "Earth"
        MICRO = "microgravity", "Microgravity"
        PARTIAL = "partial", "Partial gravity"
        HYPER = "hypergravity", "Hypergravity"
        UNKNOWN = "unknown", "Unknown"

    identifier = models.CharField(max_length=80, unique=True)
    participant = models.ForeignKey(Participant, on_delete=models.PROTECT, related_name="sessions")
    authorized_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="monitoring_sessions")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    gravity_context = models.CharField(max_length=20, choices=Gravity, default=Gravity.UNKNOWN)
    gravity_context_source = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F("started_at")), name="session_end_after_start")]

    def __str__(self):
        return self.identifier


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


class SessionDevice(UUIDPrimaryKeyModel):
    session = models.ForeignKey(MonitoringSession, on_delete=models.PROTECT, related_name="device_assignments")
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="session_assignments")
    assigned_at = models.DateTimeField()
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(released_at__isnull=True) | Q(released_at__gt=F("assigned_at")), name="assignment_end_after_start"),
            models.UniqueConstraint(fields=["session", "device", "assigned_at"], name="unique_assignment_start"),
            models.UniqueConstraint(fields=["device"], condition=Q(released_at__isnull=True), name="one_open_assignment_per_device"),
        ]
        indexes = [models.Index(fields=["device", "assigned_at"])]

    def clean(self):
        if not self.device_id or not self.session_id or not self.assigned_at:
            return
        if self.assigned_at < self.session.started_at or (
            self.session.ended_at and (not self.released_at or self.released_at > self.session.ended_at)
        ):
            raise ValidationError("Assignment must be within the monitoring session.")
        overlaps = SessionDevice.objects.filter(device_id=self.device_id).exclude(pk=self.pk)
        overlaps = overlaps.filter(Q(released_at__isnull=True) | Q(released_at__gt=self.assigned_at))
        if self.released_at:
            overlaps = overlaps.filter(assigned_at__lt=self.released_at)
        if overlaps.exists():
            raise ValidationError("Device assignments cannot overlap.")


class CounterEpoch(UUIDPrimaryKeyModel):
    """One reference period of a device counter; values are never summed here."""

    identifier = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    assignment = models.ForeignKey(SessionDevice, on_delete=models.PROTECT, related_name="counter_epochs")
    sensor = models.ForeignKey(Sensor, on_delete=models.PROTECT, related_name="counter_epochs")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    reference = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F("started_at")), name="epoch_end_after_start"),
            models.UniqueConstraint(fields=["assignment", "sensor"], condition=Q(ended_at__isnull=True), name="one_open_epoch_per_sensor_assignment"),
        ]

    def clean(self):
        if self.sensor_id and self.assignment_id and self.sensor.device_id != self.assignment.device_id:
            raise ValidationError("Counter sensor must belong to the assigned device.")
        if self.assignment_id and self.started_at:
            if self.started_at < self.assignment.assigned_at or (self.assignment.released_at and self.started_at >= self.assignment.released_at):
                raise ValidationError("Counter epoch must start within the assignment.")
            if self.ended_at and self.assignment.released_at and self.ended_at > self.assignment.released_at:
                raise ValidationError("Counter epoch cannot end after the assignment.")
        if self.assignment_id and self.sensor_id and self.started_at:
            overlaps = CounterEpoch.objects.filter(assignment_id=self.assignment_id, sensor_id=self.sensor_id).exclude(pk=self.pk)
            overlaps = overlaps.filter(Q(ended_at__isnull=True) | Q(ended_at__gt=self.started_at))
            if self.ended_at:
                overlaps = overlaps.filter(started_at__lt=self.ended_at)
            if overlaps.exists():
                raise ValidationError("Counter epochs cannot overlap.")


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


class AnalysisResult(UUIDPrimaryKeyModel):
    class Kind(models.TextChoices):
        HRV = "hrv", "Heart rate variability"
        HEART_RHYTHM = "heart_rhythm_pattern", "Heart rhythm pattern"
        RESPIRATORY_PATTERN = "respiratory_pattern", "Respiratory pattern"
        THERMAL_VARIATION = "thermal_variation", "Thermal variation"
        MISSION_TEMPERATURE_TREND = "mission_temperature_trend", "Mission temperature trend"
        PHYSICAL_ACTIVITY = "physical_activity", "Physical activity"
        INACTIVITY = "inactivity_period", "Inactivity period"

    session = models.ForeignKey(MonitoringSession, on_delete=models.PROTECT, related_name="analyses")
    sensor = models.ForeignKey(Sensor, null=True, blank=True, on_delete=models.PROTECT, related_name="analyses")
    kind = models.CharField(max_length=40, choices=Kind)
    input_source = models.CharField(max_length=12, choices=Device.Source)
    window_started_at = models.DateTimeField()
    window_ended_at = models.DateTimeField()
    numeric_value = models.DecimalField(max_digits=30, decimal_places=12, null=True, blank=True)
    unit = models.CharField(max_length=20, blank=True)
    label = models.CharField(max_length=120, blank=True)
    method = models.CharField(max_length=80)
    method_version = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(window_ended_at__gt=F("window_started_at")), name="analysis_window_order"),
            models.CheckConstraint(condition=Q(numeric_value__isnull=False) | ~Q(label=""), name="analysis_has_result"),
        ]
        indexes = [models.Index(fields=["session", "kind", "window_started_at"])]
