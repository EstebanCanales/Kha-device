"""Explicitly versioned derived results; these records imply no active analysis."""

from django.db import models
from django.db.models import F, Q

from .participants import MonitoringSession
from .sensors import Device, Sensor
from .shared import UUIDPrimaryKeyModel


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
